with spine as (
    select cast(d as date) as date_day
    from generate_series(date '2016-01-01', date '2018-12-31', interval 1 day) t(d)
)
select
    date_day,
    cast(strftime(date_day, '%Y%m%d') as integer)      as date_key,
    year(date_day)                                     as year,
    quarter(date_day)                                  as quarter,
    month(date_day)                                    as month,
    strftime(date_day, '%Y-%m')                        as year_month,
    date_trunc('month', date_day)                      as month_start,
    date_trunc('week', date_day)                       as week_start,
    strftime(date_day, '%b')                           as month_name,
    dayofweek(date_day)                                as day_of_week,
    strftime(date_day, '%a')                           as day_name,
    dayofweek(date_day) in (0, 6)                      as is_weekend,
    year(date_day) * 100 + quarter(date_day)           as year_quarter_key
from spine
