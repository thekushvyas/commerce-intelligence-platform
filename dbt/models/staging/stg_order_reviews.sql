-- The raw file contains duplicate review_ids and multiple reviews per order.
-- Keep the most recent answered review per order so review grain == order grain.
with src as (
    select
        review_id,
        order_id,
        cast(review_score as integer)                       as review_score,
        nullif(trim(review_comment_title), '')              as review_title,
        nullif(trim(review_comment_message), '')            as review_message,
        try_cast(review_creation_date as timestamp)         as review_created_at,
        try_cast(review_answer_timestamp as timestamp)      as review_answered_at
    from {{ source('olist_raw', 'olist_order_reviews_dataset') }}
),
ranked as (
    select *,
           row_number() over (partition by order_id order by review_answered_at desc nulls last, review_id) as rn
    from src
)
select
    review_id, order_id, review_score, review_title, review_message,
    review_created_at, review_answered_at,
    review_message is not null                       as has_comment,
    length(review_message)                           as comment_length,
    review_score <= 2                                as is_detractor,
    review_score >= 4                                as is_promoter
from ranked
where rn = 1
