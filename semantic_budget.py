# semantic_budget.py (Nutrition-aware, Replit-ready)
# Adds HF sentence-transformers for semantic retrieval, budget substitution, and optional LLM explanation.
# Updated to use GroceryDataset_with_Nutrition.csv with nutrition fields if present.
#
# Env vars:
#   GROCERY_CSV=/path/to/GroceryDataset_with_Nutrition.csv
#   GROCERY_CACHE_DIR=/tmp/grocery_cache (or /mnt/data/grocery_cache)
#   EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
#   USE_HF_EXPLAIN=1  (optional)
#   EXPLAIN_MODEL=google/flan-t5-small
#   HEALTH_WEIGHT=0.0..1.0   (optional extra score weight for sugar/calorie improvements; default 0)

import os
import re
import json
import math
import time
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_DATA_CSV = os.environ.get("GROCERY_CSV", "attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv")
CACHE_DIR = os.environ.get("GROCERY_CACHE_DIR", "/tmp/grocery_cache")
EMB_PATH = os.path.join(CACHE_DIR, "embeddings.npy")
IDX_PATH = os.path.join(CACHE_DIR, "products_index.parquet")
THR_PATH = os.path.join(CACHE_DIR, "sim_threshold.json")
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

HF_EXPLAIN_MODEL = os.environ.get("EXPLAIN_MODEL", "google/flan-t5-small")
USE_HF_EXPLAIN = os.environ.get("USE_HF_EXPLAIN", "0") == "1"
HEALTH_WEIGHT = float(os.environ.get("HEALTH_WEIGHT", "0.0"))

_size_pat = re.compile(r"(\d+(\.\d+)?)\s*(oz|fl oz|ml|l|g|kg|lb|lbs|ct|count|pack|pcs?)\b", re.I)
_unit_map = {"lbs": "lb", "pcs": "pc", "count": "ct"}

_TO_G = {"g":1.0, "kg":1000.0, "lb":453.592, "oz":28.3495}
_TO_ML = {"ml":1.0, "l":1000.0, "fl oz":29.5735}

def _parse_price(s):
    if pd.isna(s): return None
    s = str(s)
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s else None
    except:
        return None

def _parse_discount(s):
    if pd.isna(s): return 0.0
    t = str(s).strip().lower()
    m = re.search(r"(\d+(\.\d+)?)\s*%", t)
    if m: return float(m.group(1))/100.0
    m2 = re.search(r"(\d+(\.\d+)?)", t)
    if not m2: return 0.0
    val = float(m2.group(1))
    return val/100.0 if val > 1.5 else val

def _extract_size(title:str) -> Tuple[Optional[float], Optional[str]]:
    if not title: return (None, None)
    m = _size_pat.search(title)
    if not m: return (None, None)
    val = float(m.group(1))
    unit = _unit_map.get(m.group(3).lower(), m.group(3).lower())
    return val, unit

def _norm_size(value: Optional[float], unit: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    if value is None or unit is None: return (None, None)
    u = unit.lower()
    if u in _TO_G:  return (value*_TO_G[u], "g")
    if u in _TO_ML: return (value*_TO_ML[u], "ml")
    if u in ("ct","pc","pack"): return (value, u)
    return (None, None)

def _size_ratio(a:Tuple[Optional[float],Optional[str]], b:Tuple[Optional[float],Optional[str]]) -> Optional[float]:
    (va,ua),(vb,ub) = a,b
    if va is None or vb is None or ua is None or ub is None: return None
    if ua!=ub or vb==0: return None
    return va/ vb

def _build_text(row:pd.Series) -> str:
    title = str(row.get("Title") or "")
    subc  = str(row.get("Sub Category") or "")
    feat  = str(row.get("Feature") or "").replace("\n"," ")[:120]
    desc  = str(row.get("Product Description") or "").replace("\n"," ")[:180]
    sizev = row.get("_size_value"); sizeu = row.get("_size_unit")
    if pd.notna(sizev) and pd.notna(sizeu):
        size_str = f"{int(sizev) if float(sizev).is_integer() else round(float(sizev),2)}{sizeu}"
    else:
        size_str = "UNK"

    # Nutrition short string if present
    nutr_cols = ["Calories","Sugar_g","Protein_g","Sodium_mg","Fat_g","Carbs_g"]
    parts = []
    for c in nutr_cols:
        if c in row and pd.notna(row[c]):
            v = row[c]
            try:
                v = float(v)
                if v.is_integer(): v = int(v)
            except: pass
            parts.append(f"{c}:{v}")
    nutr_str = "; ".join(parts) if parts else "NA"

    return f"TITLE: {title} || SUBCAT: {subc} || TAGS: {feat} || DESC: {desc} || SIZE: {size_str} || NUTR: {nutr_str}"

def _load_sentence_model():
    from sentence_transformers import SentenceTransformer
    import torch
    # Fix for torch meta tensor issue - load model first, then move to device
    # Don't specify device in constructor to avoid meta tensor issues
    try:
        model = SentenceTransformer(MODEL_NAME)
        # Move to CPU after loading to avoid meta tensor issues
        model = model.to('cpu')
    except Exception as e:
        print(f"Warning: Error loading sentence transformer: {e}")
        # Fallback: try with explicit device parameter
        model = SentenceTransformer(MODEL_NAME, device='cpu', trust_remote_code=True)
    return model

def _compute_embeddings(texts:List[str], model=None, batch_size:int=64) -> np.ndarray:
    if model is None:
        model = _load_sentence_model()
    emb = model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(emb, dtype=np.float32)

def _auto_similarity_threshold(df:pd.DataFrame, emb:np.ndarray, sample:int=300, q:float=0.08, seed:int=42) -> float:
    rng = np.random.default_rng(seed)
    n = len(df)
    if n < 20: return 0.55
    idx = rng.choice(n, size=min(sample,n-1), replace=False)
    pos = []
    for i in idx:
        same = df.index[(df["Sub Category"]==df["Sub Category"].iloc[i]) & (df.index!=i)].to_numpy()
        if same.size>0:
            j = int(rng.choice(same))
            pos.append(float(emb[i] @ emb[j]))
    if len(pos)<5: return 0.55
    thr = float(np.quantile(np.array(pos), q))
    return max(min(thr, 0.9), 0.4)

def ensure_index(csv_path: Optional[str]=None, cache_dir: Optional[str]=None) -> Dict[str, Any]:
    csv_path = csv_path or DEFAULT_DATA_CSV
    cache = cache_dir or CACHE_DIR
    os.makedirs(cache, exist_ok=True)

    need_build = not (os.path.exists(IDX_PATH) and os.path.exists(EMB_PATH) and os.path.exists(THR_PATH))
    if not need_build:
        try:
            df = pd.read_parquet(IDX_PATH)
            emb = np.load(EMB_PATH)
            thr_meta = json.load(open(THR_PATH,"r"))
            return {"df": df, "emb": emb, "threshold": float(thr_meta.get("threshold",0.6))}
        except Exception:
            need_build = True

    df = pd.read_csv(csv_path)
    # Parse numeric price
    df["_price_num"] = df["Price"].apply(_parse_price)
    df["_discount_frac"] = df["Discount"].apply(_parse_discount)
    df["_price_final"] = df["_price_num"] * (1 - df["_discount_frac"])

    # Extract & normalize size
    size_vals, size_units = [], []
    for t in df["Title"].fillna(""):
        v,u = _extract_size(t)
        if v is not None and u is not None:
            nv,nu = _norm_size(v,u)
        else:
            nv,nu = (None,None)
        size_vals.append(nv); size_units.append(nu)
    df["_size_value"] = size_vals
    df["_size_unit"]  = size_units

    # Text for embeddings (now includes nutrition if present)
    df["_text"] = df.apply(_build_text, axis=1)
    
    # Generate product IDs using the SAME method as main.py (blake2b hash)
    # This ensures product IDs match between CF, semantic, and PRODUCTS_DF
    def generate_product_id(row):
        key = f"{row['Title']}|{row['Sub Category']}"
        hash_bytes = hashlib.blake2b(key.encode('utf-8'), digest_size=8).digest()
        return int.from_bytes(hash_bytes, 'big', signed=False) & ((1 << 63) - 1)
    
    df["product_id"] = df.apply(generate_product_id, axis=1)

    # Keep valid rows
    df = df[df["_price_final"].notna()].reset_index(drop=True)

    # Embeddings
    emb = _compute_embeddings(df["_text"].tolist())

    # Threshold
    thr = _auto_similarity_threshold(df, emb)

    # Save cache
    df.to_parquet(IDX_PATH, index=False)
    np.save(EMB_PATH, emb)
    with open(THR_PATH,"w") as f:
        json.dump({"threshold": thr, "model": MODEL_NAME, "built_at": time.time()}, f)

    return {"df": df, "emb": emb, "threshold": thr}

_GLOBAL = {"df": None, "emb": None, "threshold": 0.6, "model": None, "explainer": None, "elastic_optimizer": None}

def _get_model():
    if _GLOBAL["model"] is None:
        _GLOBAL["model"] = _load_sentence_model()
    return _GLOBAL["model"]

def _encode(texts:List[str]) -> np.ndarray:
    mdl = _get_model()
    return _compute_embeddings(texts, model=mdl)

def _maybe_explainer():
    if _GLOBAL["explainer"] is not None:
        return _GLOBAL["explainer"]
    if not USE_HF_EXPLAIN:
        _GLOBAL["explainer"] = None
        return None
    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
        tok = AutoTokenizer.from_pretrained(HF_EXPLAIN_MODEL)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(HF_EXPLAIN_MODEL)
        pipe = pipeline("text2text-generation", model=mdl, tokenizer=tok)
        _GLOBAL["explainer"] = pipe
    except Exception:
        _GLOBAL["explainer"] = None
    return _GLOBAL["explainer"]

def _get_elastic_optimizer():
    """Load Elastic Net optimizer for feature weighting, or use defaults."""
    if _GLOBAL["elastic_optimizer"] is not None:
        return _GLOBAL["elastic_optimizer"]
    
    try:
        from elastic_budget_optimizer import BudgetElasticNetOptimizer
        optimizer = BudgetElasticNetOptimizer.load('ml_data/budget_elasticnet.pkl')
        _GLOBAL["elastic_optimizer"] = optimizer
        return optimizer
    except Exception:
        # Fall back to None (use default weights)
        _GLOBAL["elastic_optimizer"] = None
        return None

def _template_explain(slots:Dict[str,Any]) -> str:
    tags = set([t.lower() for t in slots.get("tags",[])])
    subcat = slots.get("subcat","same category")
    save = slots.get("save",0.0)
    sr = slots.get("size_ratio",None)
    if "no_size" in tags:
        return f"Same category ({subcat}), no size comparison available, saves ${save:.2f} per unit"
    if "size_close" in tags and sr is not None:
        return f"Same category ({subcat}), similar size (×{sr:.2f}), lower unit price, saves ${save:.2f}"
    if "health_better" in tags:
        return f"Same category ({subcat}), lower sugar/calories and saves ${save:.2f}"
    return f"Same category ({subcat}), similar function and cheaper, saves ${save:.2f}"

def _explain(slots:Dict[str,Any]) -> str:
    pipe = _maybe_explainer()
    if pipe is None:
        return _template_explain(slots)
    prompt = (
        "You are a shopping assistant. Generate a brief explanation in 20 words or less based on facts.\n"
        f"Facts: Original: {slots.get('src_name')}; Candidate: {slots.get('cand_name')}; "
        f"Category: {slots.get('subcat')}; Size ratio: {slots.get('size_ratio','unknown')}; "
        f"Similarity: {slots.get('similarity'):.2f}; Expected savings: ${slots.get('save'):.2f}; "
        f"Tags: {','.join(slots.get('tags',[]))}\nOutput:"
    )
    try:
        out = pipe(prompt, max_new_tokens=32, num_beams=2)[0]["generated_text"]
        return out.strip().strip('"').replace("\n"," ")
    except Exception:
        return _template_explain(slots)

def _norm01(x:float, ref:float) -> float:
    if ref <= 0: return 0.0
    return max(0.0, min(1.0, x / ref))

@dataclass
class Candidate:
    src_idx: int
    cand_idx: int
    saving: float
    similarity: float
    size_ratio: Optional[float]
    health_gain: float
    score: float
    reason_tags: List[str]

def _collect_candidates_for_item(df:pd.DataFrame, emb:np.ndarray, item_text:str, item_price:float,
                                 item_subcat:str, item_size:Tuple[Optional[float],Optional[str]],
                                 item_nutr:Dict[str,float],
                                 topk:int=100, sim_threshold:float=0.50) -> List[Candidate]:
    q = _encode([item_text])[0]
    
    # FIXED: Try same subcategory first, then expand to related categories
    # This prevents "0 recommendations" when no exact subcategory matches exist
    mask = (df["Sub Category"]==item_subcat).to_numpy()
    idxs = np.where(mask)[0]
    print(f"[BUDGET DEBUG]   Items in same category '{item_subcat}': {idxs.size}")
    
    # If no matches in same subcategory, try broader category (first word of subcategory)
    # e.g., "Meat & Seafood" → look for any "Meat" items
    if idxs.size == 0 and item_subcat:
        # Extract main category (e.g., "Snacks" from "Snacks & Candy")
        main_cat = item_subcat.split('&')[0].split(',')[0].strip()
        mask = df["Sub Category"].str.contains(main_cat, case=False, na=False).to_numpy()
        idxs = np.where(mask)[0]
        print(f"[BUDGET DEBUG]   Items in broader category '{main_cat}': {idxs.size}")
    
    # If still no matches, allow cross-category (but lower priority via reduced similarity threshold)
    if idxs.size == 0:
        idxs = np.arange(len(df))
        sim_threshold = max(0.65, sim_threshold)  # Require higher similarity for cross-category
        print(f"[BUDGET DEBUG]   No category match, searching all {idxs.size} products with threshold {sim_threshold:.2f}")
    
    sims = (emb[idxs] @ q).astype(np.float32)
    # preselect by sim
    ok = np.where(sims >= sim_threshold)[0]
    print(f"[BUDGET DEBUG]   Items with similarity >= {sim_threshold:.2f}: {ok.size}")
    if ok.size == 0:
        return []
    if ok.size > topk:
        sel = np.argpartition(-sims[ok], topk)[:topk]
        sims_sel = sims[ok][sel]; idxs_sel = idxs[ok][sel]
    else:
        sims_sel = sims[ok]; idxs_sel = idxs[ok]

    cands: List[Candidate] = []
    cheaper_count = 0
    for sim, j in zip(sims_sel.tolist(), idxs_sel.tolist()):
        price_j = float(df["_price_final"].iloc[j])
        if price_j >= item_price:
            continue
        cheaper_count += 1
        sj = (df["_size_value"].iloc[j], df["_size_unit"].iloc[j])
        sr = _size_ratio(item_size, sj)
        tags = ["same_subcat"]
        if sr is None:
            tags.append("no_size")
        elif 0.6 <= sr <= 1.4:
            tags.append("size_close")
        elif sr < 0.6:
            tags.append("size_smaller")
        else:
            tags.append("size_larger")

        # Optional health gain: if candidate sugar <= source sugar and calories <= source calories
        hg = 0.0
        sugar_src = item_nutr.get("Sugar_g")
        cal_src   = item_nutr.get("Calories")
        sugar_c   = df["Sugar_g"].iloc[j] if "Sugar_g" in df.columns else None
        cal_c     = df["Calories"].iloc[j] if "Calories" in df.columns else None
        if sugar_src is not None and sugar_c is not None and cal_src is not None and cal_c is not None:
            try:
                sugar_improve = 1.0 if float(sugar_c) <= float(sugar_src) else 0.0
                cal_improve   = 1.0 if float(cal_c)   <= float(cal_src)   else 0.0
                hg = 0.5*sugar_improve + 0.5*cal_improve  # in [0,1]
                if hg > 0:
                    tags.append("health_better")
            except:
                pass

        saving = (item_price - price_j)
        cands.append(Candidate(src_idx=-1, cand_idx=j, saving=saving, similarity=float(sim), size_ratio=sr, health_gain=hg, score=0.0, reason_tags=tags))
    print(f"[BUDGET DEBUG]   Cheaper items found: {cheaper_count} (price < ${item_price:.2f})")
    return cands

def recommend_substitutions(cart: List[Dict[str,Any]], budget: float,
                            lam: float=0.6, sim_threshold: Optional[float]=None,
                            buffer_ratio: float=0.05, buffer_min: float=1.0,
                            topk:int=100) -> Dict[str,Any]:
    """
    cart item format:
      - title (str)
      - subcat (str)
      - price (float)
      - qty (int)
      - size_value (float|None)
      - size_unit (str|None)
      - nutrition (dict|None): {"Calories":..., "Sugar_g":..., etc}
    """
    if _GLOBAL["df"] is None:
        idx = ensure_index()
        _GLOBAL.update(idx)
    
    df = _GLOBAL["df"]
    emb = _GLOBAL["emb"]
    thr = sim_threshold or _GLOBAL["threshold"]

    # compute cart total
    total = sum(float(item.get("price",0.0)) * int(item.get("qty",1)) for item in cart)
    buffer = max(buffer_min, buffer_ratio * budget)
    
    print(f"[BUDGET DEBUG] Total: ${total:.2f}, Budget: ${budget:.2f}, Buffer: ${buffer:.2f}")
    
    if total <= budget + buffer:
        return {"total": total, "budget": budget, "suggestions": [], "message": f"Current total ${total:.2f} is within budget"}

    target_savings = total - budget + buffer
    print(f"[BUDGET DEBUG] Need to save: ${target_savings:.2f}")
    
    # Focus on the LAST cart item (most recently added) when already over budget
    # This provides dynamic recommendations as user adds items to an over-budget cart
    all_cands: List[Candidate] = []
    
    # Only process the last item in the cart (most recent addition)
    if cart:
        i = len(cart) - 1  # Last item index
        item = cart[-1]  # Most recently added item
        
        title = str(item.get("title",""))
        subcat = str(item.get("subcat",""))
        price = float(item.get("price",0.0))
        qty = int(item.get("qty",1))
        sv = item.get("size_value"); su = item.get("size_unit")
        size = (float(sv) if sv is not None else None, str(su) if su is not None else None)
        nutr = item.get("nutrition") or {}
        
        print(f"[BUDGET DEBUG] Processing last cart item: '{title}' (${price:.2f}) in '{subcat}'")
        
        text = _build_text(pd.Series({"Title":title, "Sub Category":subcat, "Feature":"", "Product Description":"", "_size_value":size[0], "_size_unit":size[1], **nutr}))
        
        cands = _collect_candidates_for_item(df, emb, text, price, subcat, size, nutr, topk, thr)
        print(f"[BUDGET DEBUG] Found {len(cands)} cheaper alternatives")
        
        for c in cands:
            c.src_idx = i
            c.saving *= qty  # scale by quantity
        all_cands.extend(cands)
    
    if not all_cands:
        print(f"[BUDGET DEBUG] No suitable substitutes found for any items")
        return {"total": total, "budget": budget, "suggestions": [], "message": f"No suitable substitutes found, current total ${total:.2f}"}
    
    # Score candidates using Elastic Net optimizer if available
    elastic_opt = _get_elastic_optimizer()
    max_save = max(c.saving for c in all_cands) if all_cands else 1.0
    
    for c in all_cands:
        save_score = _norm01(c.saving, max_save)
        sim_score = c.similarity
        health_score = c.health_gain
        size_score = 1.0 if (c.size_ratio and 0.8 <= c.size_ratio <= 1.2) else 0.5
        
        # Use Elastic Net learned weights if available, otherwise use lambda
        if elastic_opt and elastic_opt.is_trained:
            c.score = elastic_opt.compute_score(save_score, sim_score, health_score, size_score)
        else:
            # Fallback to original lambda-based scoring
            c.score = lam * save_score + (1-lam) * sim_score + HEALTH_WEIGHT * health_score
    
    # Sort and pick top candidates
    all_cands.sort(key=lambda x: x.score, reverse=True)
    
    suggestions = []
    item_replacement_count = {}  # Track how many replacements we've suggested per item
    accum_save = 0.0
    
    for c in all_cands:
        # Allow up to 3 replacement options per cart item
        if item_replacement_count.get(c.src_idx, 0) >= 3:
            continue
        if len(suggestions) >= 10:  # Increased max suggestions
            break
        
        src_item = cart[c.src_idx]
        cand_row = df.iloc[c.cand_idx]
        
        slots = {
            "src_name": src_item["title"],
            "cand_name": str(cand_row["Title"]),
            "subcat": str(cand_row["Sub Category"]),
            "size_ratio": c.size_ratio,
            "similarity": c.similarity,
            "save": c.saving,
            "tags": c.reason_tags
        }
        reason = _explain(slots)
        
        # Build full product details for replacement item
        replacement_product = {
            "title": str(cand_row["Title"]),
            "subcat": str(cand_row["Sub Category"]),
            "price": float(cand_row["_price_final"]),
            "qty": src_item["qty"],  # Keep same quantity
            "size_value": float(cand_row["_size_value"]) if pd.notna(cand_row.get("_size_value")) else None,
            "size_unit": str(cand_row["_size_unit"]) if pd.notna(cand_row.get("_size_unit")) else None,
            "feature": str(cand_row.get("Feature", "")),
            "desc": str(cand_row.get("Product Description", ""))
        }
        # Add nutrition if available
        nutr = {}
        for k in ["Calories","Sugar_g","Protein_g","Sodium_mg","Fat_g","Carbs_g"]:
            if k in cand_row and pd.notna(cand_row[k]):
                try:
                    nutr[k] = float(cand_row[k])
                except:
                    pass
        if nutr:
            replacement_product["nutrition"] = nutr
        
        suggestions.append({
            "replace": src_item["title"],
            "with": str(cand_row["Title"]),
            "expected_saving": f"{c.saving:.2f}",
            "similarity": f"{c.similarity:.2f}",
            "reason": reason,
            "replacement_product": replacement_product  # Full product details
        })
        
        # Track replacements per item
        item_replacement_count[c.src_idx] = item_replacement_count.get(c.src_idx, 0) + 1
        accum_save += c.saving
    
    msg = f"Current total ${total:.2f}, over budget by ${total-budget:.2f}. Recommended {len(suggestions)} substitutes can save about ${accum_save:.2f}"
    
    return {
        "total": total,
        "budget": budget,
        "over_budget": total - budget,
        "suggestions": suggestions,
        "message": msg
    }