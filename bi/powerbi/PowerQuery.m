// Power BI - Power Query (M) loaders for the Commerce Intelligence star schema.
// Setup: Home > Transform data > New parameter  ->  DataFolder (Text) = full path to this repo's data/marts folder
// (parquet, committed) or bi/data (csv, produced by `make bi`). Then create one blank query per table below.
// Power BI reads Parquet natively (Parquet.Document) - no drivers needed.

// ---- parameter ----
// DataFolder = "C:\Users\you\commerce-intelligence-platform\data\marts"

// ---- helper: load a parquet mart ----
// (fnLoadMart)
(tableName as text) as table =>
let
    Source = Parquet.Document(File.Contents(DataFolder & "\" & tableName & ".parquet")),
    Typed  = Table.TransformColumnTypes(Source, List.Transform(Table.ColumnNames(Source), each {_, Table.Column(Source, _){0} is date ?? type any}))
in
    Source

// ---- tables ----
// FactOrders
let Source = fnLoadMart("fact_orders"),
    Dated  = Table.TransformColumnTypes(Source, {{"purchase_date", type date}, {"purchased_at", type datetime}, {"delivered_at", type datetime}, {"estimated_delivery_at", type datetime}})
in  Dated

// FactOrderItems
let Source = fnLoadMart("fact_order_items") in Source

// DimCustomer
let Source = fnLoadMart("dim_customer") in Source

// DimSeller
let Source = fnLoadMart("dim_seller") in Source

// DimProduct
let Source = fnLoadMart("dim_product") in Source

// DimDate  (mark as date table: Table tools > Mark as date table > date_day)
let Source = fnLoadMart("dim_date"), Typed = Table.TransformColumnTypes(Source, {{"date_day", type date}}) in Typed

// DimGeography
let Source = fnLoadMart("dim_geography") in Source

// FactSellerFunnel
let Source = fnLoadMart("fact_seller_funnel") in Source

// CustomerScores (RFM segment, CLV, cluster) - csv produced by `make bi`
let Source = Csv.Document(File.Contents(DataFolder & "\..\..\bi\data\customer_scores.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in  Promoted

// OrderRiskScores (p_late per order)
let Source = Csv.Document(File.Contents(DataFolder & "\..\..\bi\data\order_risk_scores.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"p_late", type number}})
in  Typed
