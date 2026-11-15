-- 1M raw coordinate pings collapsed to one centroid per zip prefix, bounded to Brazil.
select
    lpad(geolocation_zip_code_prefix, 5, '0')          as zip_prefix,
    avg(cast(geolocation_lat as double))               as lat,
    avg(cast(geolocation_lng as double))               as lng,
    mode(lower(trim(geolocation_city)))                as city,
    mode(upper(trim(geolocation_state)))               as state,
    count(*)                                           as n_points
from {{ source('olist_raw', 'olist_geolocation_dataset') }}
where cast(geolocation_lat as double) between -34 and 6
  and cast(geolocation_lng as double) between -74 and -34
group by 1
