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

# Silver: types, de-duplication, quality rules with a quarantine, and PII redaction.
# PySpark twin of src/fabricbi/coldpath/silver.py (written for Fabric, not executed offline).
from pyspark.sql import functions as F

products = spark.table("silver__products").select("sku")
stores = spark.table("silver__stores").select("store_id")
pos = spark.table("bronze__pos_lines").dropDuplicates(["txn_id", "line_no", "sku", "qty"])
typed = pos.select(
    "txn_id",
    F.col("line_no").cast("int").alias("line_no"),
    "store_id",
    F.to_timestamp("ts").alias("ts"),
    F.when(F.col("customer_id") == "", None).otherwise(F.col("customer_id")).alias("customer_id"),
    "sku",
    F.col("qty").cast("int").alias("qty"),
    F.col("unit_price").cast("double").alias("unit_price"),
    F.col("discount_pct").cast("double").alias("discount_pct"),
)
checked = (
    typed.join(products.withColumn("_sku_ok", F.lit(True)), "sku", "left")
    .join(stores.withColumn("_store_ok", F.lit(True)), "store_id", "left")
    .withColumn(
        "_dq_rule",
        F.when(~F.col("qty").between(1, 50), "range:qty")
        .when(F.col("_sku_ok").isNull(), "fk:sku->products")
        .when(F.col("_store_ok").isNull(), "fk:store_id->stores"),
    )
    .drop("_sku_ok", "_store_ok")
)
checked.filter("_dq_rule IS NULL").drop("_dq_rule").write.mode("overwrite").format("delta").saveAsTable("silver__pos_lines")
checked.filter("_dq_rule IS NOT NULL").write.mode("overwrite").format("delta").saveAsTable("silver__pos_lines_quarantine")

email = r"[\w.+-]+@[\w-]+\.[\w.]+"
phone = r"\b\d{3}-\d{3,4}-\d{4}\b"
tickets = spark.table("bronze__support_tickets").select(
    "ticket_id", "store_id", F.to_date("opened").alias("opened"), "channel",
    F.regexp_replace(F.regexp_replace("text", email, "[EMAIL]"), phone, "[PHONE]").alias("text_redacted"),
)
tickets.write.mode("overwrite").format("delta").saveAsTable("silver__support_tickets")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
