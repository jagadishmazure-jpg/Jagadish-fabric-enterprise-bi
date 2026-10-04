# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse_name": "lh_retail"
# META     }
# META   }
# META }

# CELL ********************

# Gold: star schema with stable surrogate keys, then the daily aggregate.
# PySpark twin of src/fabricbi/coldpath/gold.py (written for Fabric, not executed offline).
from pyspark.sql import Window
from pyspark.sql import functions as F


def keyed(df, natural, key):
    return df.withColumn(key, F.row_number().over(Window.orderBy(natural)))


dim_store = keyed(spark.table("silver__stores"), "store_id", "store_key")
dim_product = keyed(spark.table("silver__products"), "sku", "product_key")
dim_store.write.mode("overwrite").format("delta").saveAsTable("gold__dim_store")
dim_product.write.mode("overwrite").format("delta").saveAsTable("gold__dim_product")

pos = spark.table("silver__pos_lines")
fact = (
    pos.join(dim_store.select("store_id", "store_key"), "store_id")
    .join(dim_product.select("sku", "product_key", "unit_cost"), "sku")
    .select(
        F.concat_ws("-", "txn_id", "line_no").alias("sales_line_id"),
        "txn_id",
        F.date_format("ts", "yyyyMMdd").cast("int").alias("date_key"),
        "store_key",
        "product_key",
        "qty",
        F.round(F.col("qty") * F.col("unit_price") * (1 - F.col("discount_pct")), 2).alias("net_amount"),
        F.round(F.col("qty") * F.col("unit_cost"), 2).alias("cost_amount"),
    )
)
fact.write.mode("overwrite").format("delta").saveAsTable("gold__fact_sales")

agg = (
    fact.join(dim_product.select("product_key", "category"), "product_key")
    .groupBy("date_key", "store_key", "category")
    .agg(F.round(F.sum("net_amount"), 2).alias("net_sales"), F.sum("qty").alias("units"), F.countDistinct("txn_id").alias("transactions"))
)
agg.write.mode("overwrite").format("delta").saveAsTable("gold__agg_daily_sales")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
