-- Calculate and insert replenishment cycles for demo data

-- First, identify replenishable products (products purchased 2+ times)
INSERT INTO replenishable_products (product_id, product_title, unit_metadata, purchase_frequency, last_updated)
SELECT DISTINCT
    oi.product_id,
    oi.product_title,
    '{"unit": "each", "size": 1}'::json as unit_metadata,
    COUNT(DISTINCT o.id) / 
        NULLIF(EXTRACT(EPOCH FROM (MAX(o.created_at) - MIN(o.created_at))) / 86400.0, 0) as purchase_frequency,
    NOW() as last_updated
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
WHERE o.user_id = 2
GROUP BY oi.product_id, oi.product_title
HAVING COUNT(DISTINCT o.id) >= 2
ON CONFLICT (product_id) DO UPDATE
SET purchase_frequency = EXCLUDED.purchase_frequency,
    last_updated = EXCLUDED.last_updated;

-- Calculate user replenishment cycles
WITH purchase_intervals AS (
    SELECT 
        o.user_id,
        oi.product_id,
        oi.product_title,
        oi.product_subcat,
        oi.unit_price,
        o.created_at,
        LAG(o.created_at) OVER (PARTITION BY o.user_id, oi.product_id ORDER BY o.created_at) as prev_purchase,
        EXTRACT(EPOCH FROM (o.created_at - LAG(o.created_at) OVER (PARTITION BY o.user_id, oi.product_id ORDER BY o.created_at))) / 86400.0 as days_between
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.user_id = 2
),
median_intervals AS (
    SELECT 
        user_id,
        product_id,
        product_title,
        product_subcat,
        unit_price,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_between) as median_interval,
        MAX(created_at) as last_purchase_date,
        COUNT(*) as purchase_count
    FROM purchase_intervals
    WHERE days_between IS NOT NULL
    GROUP BY user_id, product_id, product_title, product_subcat, unit_price
    HAVING COUNT(*) >= 1
)
INSERT INTO user_replenishment_cycles (
    user_id, product_id, product_title, product_subcat, product_price,
    interval_days, last_purchase_date, next_due_date, is_active
)
SELECT 
    user_id,
    product_id,
    product_title,
    product_subcat,
    unit_price,
    ROUND(median_interval::numeric, 1)::integer as interval_days,
    last_purchase_date,
    (last_purchase_date + (ROUND(median_interval::numeric) || ' days')::interval) as next_due_date,
    TRUE as is_active
FROM median_intervals
ON CONFLICT (user_id, product_id) DO UPDATE
SET interval_days = EXCLUDED.interval_days,
    last_purchase_date = EXCLUDED.last_purchase_date,
    next_due_date = EXCLUDED.next_due_date,
    updated_at = NOW();
