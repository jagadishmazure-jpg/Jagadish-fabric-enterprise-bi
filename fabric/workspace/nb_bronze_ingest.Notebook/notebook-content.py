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

# Bronze: land the day's files from the landing zone shortcut, every column as text, with ingest
# metadata. PySpark twin of src/fabricbi/coldpath/bronze.py (written for Fabric, not executed offline).
from pyspark.sql import functions as F

batch_id = spark.conf.get("spark.fabricbi.batch_id", "manual")
sources = {
    "pos_lines": ("Files/landing/pos/*.csv", "csv"),
    "freezer_readings": ("Files/landing/freezer/*.csv", "csv"),
    "support_tickets": ("Files/landing/tickets/*.jsonl", "json"),
}
for table, (path, fmt) in sources.items():
    reader = spark.read.option("header", True).option("inferSchema", False) if fmt == "csv" else spark.read
    df = reader.format(fmt).load(path)
    df = df.select([F.col(c).cast("string") for c in df.columns])
    df = (
        df.withColumn("_row_hash", F.sha2(F.concat_ws("|", *df.columns), 256))
        .withColumn("_source_file", F.input_file_name())
        .withColumn("_batch_id", F.lit(batch_id))
    )
    df.write.mode("append").format("delta").saveAsTable(f"bronze__{table}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
