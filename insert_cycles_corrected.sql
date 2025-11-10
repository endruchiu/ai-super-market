-- Simplified: Insert replenishment cycles for demo data

-- Step 1: Insert replenishable products
INSERT INTO replenishable_products (
    product_id, product_title, product_subcat,
    avg_interval_days, total_purchases, unique_users, is_consumable, last_updated
)
SELECT 
    oi.product_id,
    oi.product_title,
    oi.product_subcat,
    AVG(EXTRACT(EPOCH FROM (o.created_at - LAG(o.created_at) OVER (PARTITION BY oi.product_id ORDER BY o.created_at))) / 86400.0) as avg_interval,
    COUNT(DISTINCT o.id) as total_purchases,
    COUNT(DISTINCT o.user_id) as unique_users,
    TRUE as is_consumable,
    NOW() as last_updated
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
WHERE o.user_id = 2
GROUP BY oi.product_id, oi.product_title, oi.product_subcat
HAVING COUNT(DISTINCT o.id) >= 2
ON CONFLICT (product_id) DO NOTHING;

-- Step 2: Insert user replenishment cycles
WITH purchase_data AS (
    SELECT 
        o.user_id,
        oi.product_id,
        oi.product_title,
        oi.product_subcat,
        MIN(o.created_at) as first_purchase,
        MAX(o.created_at) as last_purchase,
        COUNT(*) as purchase_count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (o.created_at - LAG(o.created_at) OVER (PARTITION BY o.user_id, oi.product_id ORDER BY o.created_at))) / 86400.0
        ) as median_interval
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.user_id = 2
    GROUP BY o.user_id, oi.product_id, oi.product_title, oi.product_subcat
    HAVING COUNT(*) >= 2
)
INSERT INTO user_replenishment_cycles (
    user_id, product_id, product_title, product_subcat,
    first_purchase_date, last_purchase_date, purchase_count,
    median_interval_days, adjusted_interval_days, next_due_date, is_active
)
SELECT 
    user_id,
    product_id,
    product_title,
    product_subcat,
    first_purchase,
    last_purchase,
    purchase_count,
    ROUND(median_interval::numeric, 1) as median_interval,
    ROUND(median_interval::numeric, 1) as adjusted_interval,
    (last_purchase + (ROUND(median_interval::numeric) || ' days')::interval)::date as next_due_date,
    TRUE as is_active
FROM purchase_data
WHERE median_interval IS NOT NULL
ON CONFLICT (user_id, product_id) DO UPDATE
SET median_interval_days = EXCLUDED.median_interval_days,
    adjusted_interval_days = EXCLUDED.adjusted_interval_days,
    last_purchase_date = EXCLUDED.last_purchase_date,
    next_due_date = EXCLUDED.next_due_date,
    purchase_count = EXCLUDED.purchase_count,
    updated_at = NOW();
