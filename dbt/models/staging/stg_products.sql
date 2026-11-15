with p as (
    select * from {{ source('olist_raw', 'olist_products_dataset') }}
),
t as (
    select product_category_name, product_category_name_english
    from {{ source('olist_raw', 'product_category_name_translation') }}
)
select
    p.product_id,
    coalesce(t.product_category_name_english,
             -- two categories are missing from the translation file in the public release
             case p.product_category_name
                 when 'pc_gamer' then 'pc_gamer'
                 when 'portateis_cozinha_e_preparadores_de_alimentos' then 'kitchen_portables_and_food_preparers'
                 else p.product_category_name end,
             'unknown')                                       as category,
    p.product_category_name                                   as category_pt,
    cast(p.product_name_lenght as integer)                    as name_length,
    cast(p.product_description_lenght as integer)             as description_length,
    cast(p.product_photos_qty as integer)                     as photos_qty,
    cast(p.product_weight_g as double)                        as weight_g,
    cast(p.product_length_cm as double)                       as length_cm,
    cast(p.product_height_cm as double)                       as height_cm,
    cast(p.product_width_cm as double)                        as width_cm,
    cast(p.product_length_cm as double) * cast(p.product_height_cm as double) * cast(p.product_width_cm as double) / 1000.0 as volume_litres
from p
left join t using (product_category_name)
