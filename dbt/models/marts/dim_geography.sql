-- Zip-prefix level geography with state centroids as fallback for prefixes missing from the geo file.
with zips as (
    select zip_prefix, lat, lng, city, state from {{ ref('stg_geolocation') }}
),
state_centroid as (
    select state, avg(lat) as state_lat, avg(lng) as state_lng from zips group by 1
),
all_prefixes as (
    select zip_prefix, city, state from {{ ref('stg_customers') }}
    union
    select zip_prefix, city, state from {{ ref('stg_sellers') }}
)
select
    a.zip_prefix,
    coalesce(z.city, a.city)             as city,
    a.state,
    coalesce(z.lat, s.state_lat)         as lat,
    coalesce(z.lng, s.state_lng)         as lng,
    z.lat is not null                    as has_exact_geo,
    case a.state
        when 'SP' then 'Southeast' when 'RJ' then 'Southeast' when 'MG' then 'Southeast' when 'ES' then 'Southeast'
        when 'PR' then 'South'     when 'SC' then 'South'     when 'RS' then 'South'
        when 'DF' then 'Center-West' when 'GO' then 'Center-West' when 'MT' then 'Center-West' when 'MS' then 'Center-West'
        when 'BA' then 'Northeast' when 'PE' then 'Northeast' when 'CE' then 'Northeast' when 'MA' then 'Northeast'
        when 'PB' then 'Northeast' when 'RN' then 'Northeast' when 'AL' then 'Northeast' when 'SE' then 'Northeast' when 'PI' then 'Northeast'
        when 'PA' then 'North' when 'AM' then 'North' when 'TO' then 'North' when 'RO' then 'North'
        when 'AC' then 'North' when 'AP' then 'North' when 'RR' then 'North'
        else 'Other' end                 as region
from all_prefixes a
left join zips z using (zip_prefix)
left join state_centroid s on s.state = a.state
qualify row_number() over (partition by a.zip_prefix order by z.lat is null, a.city) = 1
