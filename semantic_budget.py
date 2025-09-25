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
    return SentenceTransformer(MODEL_NAME)

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
    df["product_id"] = pd.util.hash_pandas_object(df[["Title","Sub Category"]], index=False).astype(np.int64)

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

_GLOBAL = {"df": None, "emb": None, "threshold": 0.6, "model": None, "explainer": None}

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

def _template_explain(slots:Dict[str,Any]) -> str:
    tags = set([t.lower() for t in slots.get("tags",[])])
    subcat = slots.get("subcat","同类")
    save = slots.get("save",0.0)
    sr = slots.get("size_ratio",None)
    if "no_size" in tags:
        return f"同类{subcat}，无规格可比，按单件价更省，估计省${save:.2f}"
    if "size_close" in tags and sr is not None:
        return f"同类{subcat}，规格相近(×{sr:.2f})，单价更低，估计省${save:.2f}"
    if "health_better" in tags:
        return f"同类{subcat}，更低糖/热量且更省，估计省${save:.2f}"
    return f"同类{subcat}，功能接近且更便宜，估计省${save:.2f}"

def _explain(slots:Dict[str,Any]) -> str:
    pipe = _maybe_explainer()
    if pipe is None:
        return _template_explain(slots)
    prompt = (
        "你是电商购物助手。根据事实生成<=20字中文解释，只用事实，避免臆测。\n"
        f"事实：原：{slots.get('src_name')}；候选：{slots.get('cand_name')}；"
        f"类目：{slots.get('subcat')}；规格比：{slots.get('size_ratio','未知')}；"
        f"相似度：{slots.get('similarity'):.2f}；预计节省：${slots.get('save'):.2f}；"
        f"标签：{','.join(slots.get('tags',[]))}\n输出："
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
                                 topk:int=60, sim_threshold:float=0.55) -> List[Candidate]:
    q = _encode([item_text])[0]
    mask = (df["Sub Category"]==item_subcat).to_numpy()
    idxs = np.where(mask)[0]
    if idxs.size == 0: return []
    sims = (emb[idxs] @ q).astype(np.float32)
    # preselect by sim
    ok = np.where(sims >= sim_threshold)[0]
    if ok.size == 0:
        return []
    if ok.size > topk:
        sel = np.argpartition(-sims[ok], topk)[:topk]
        sims_sel = sims[ok][sel]; idxs_sel = idxs[ok][sel]
    else:
        sims_sel = sims[ok]; idxs_sel = idxs[ok]

    cands: List[Candidate] = []
    for sim, j in zip(sims_sel.tolist(), idxs_sel.tolist()):
        price_j = float(df["_price_final"].iloc[j])
        if price_j >= item_price:
            continue
        sj = (df["_size_value"].iloc[j], df["_size_unit"].iloc[j])
        sr = _size_ratio(item_size, sj)
        tags = ["same_subcat"]
        if sr is None:
            tags.append("no_size")
        elif 0.6 <= sr <= 1.4:
            tags.append("size_close")
        else:
            continue

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
    return cands

def recommend_substitutions(cart: List[Dict[str,Any]], budget: float,
                            lam: float=0.6, sim_threshold: Optional[float]=None,
                            buffer_ratio: float=0.05, buffer_min: float=1.0,
                            topk:int=60) -> Dict[str,Any]:
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
    
    if total <= budget + buffer:
        return {"total": total, "budget": budget, "suggestions": [], "message": f"当前总价 ${total:.2f} 在预算内"}

    target_savings = total - budget + buffer
    
    # For each cart item, collect candidates
    all_cands: List[Candidate] = []
    for i, item in enumerate(cart):
        title = str(item.get("title",""))
        subcat = str(item.get("subcat",""))
        price = float(item.get("price",0.0))
        qty = int(item.get("qty",1))
        sv = item.get("size_value"); su = item.get("size_unit")
        size = (float(sv) if sv is not None else None, str(su) if su is not None else None)
        nutr = item.get("nutrition") or {}
        
        text = _build_text(pd.Series({"Title":title, "Sub Category":subcat, "Feature":"", "Product Description":"", "_size_value":size[0], "_size_unit":size[1], **nutr}))
        
        cands = _collect_candidates_for_item(df, emb, text, price, subcat, size, nutr, topk, thr)
        for c in cands:
            c.src_idx = i
            c.saving *= qty  # scale by quantity
        all_cands.extend(cands)
    
    if not all_cands:
        return {"total": total, "budget": budget, "suggestions": [], "message": f"未找到合适替代品，当前总价 ${total:.2f}"}
    
    # Score candidates
    max_save = max(c.saving for c in all_cands) if all_cands else 1.0
    for c in all_cands:
        save_score = _norm01(c.saving, max_save)
        sim_score = c.similarity
        health_score = c.health_gain
        c.score = lam * save_score + (1-lam) * sim_score + HEALTH_WEIGHT * health_score
    
    # Sort and pick top candidates
    all_cands.sort(key=lambda x: x.score, reverse=True)
    
    suggestions = []
    covered = set()
    accum_save = 0.0
    
    for c in all_cands:
        if c.src_idx in covered:
            continue
        if accum_save >= target_savings and len(suggestions) >= 3:
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
        
        suggestions.append({
            "replace": src_item["title"],
            "with": str(cand_row["Title"]),
            "expected_saving": f"{c.saving:.2f}",
            "similarity": f"{c.similarity:.2f}",
            "reason": reason
        })
        
        covered.add(c.src_idx)
        accum_save += c.saving
        
        if len(suggestions) >= 5:
            break
    
    msg = f"当前总价 ${total:.2f}，超预算 ${total-budget:.2f}。推荐 {len(suggestions)} 个替代品可省约 ${accum_save:.2f}"
    
    return {
        "total": total,
        "budget": budget,
        "over_budget": total - budget,
        "suggestions": suggestions,
        "message": msg
    }