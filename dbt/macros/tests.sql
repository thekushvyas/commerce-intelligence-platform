{% test unique_combination(model, columns) %}
    select {{ columns | join(', ') }}, count(*) as n
    from {{ model }}
    group by {{ columns | join(', ') }}
    having count(*) > 1
{% endtest %}

{% test positive_values(model, column_name) %}
    select * from {{ model }} where {{ column_name }} <= 0
{% endtest %}
