from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import psycopg2
from psycopg2.extras import execute_values
import uvicorn
import uuid

# --- 1. 配置区域 ---
DB_CONFIG = "host=localhost dbname=apple_health user=postgres password=123456 port=5432"

# 映射分类到具体的数据库表名 (白名单机制)
TABLE_MAP = {
    "heart_rate": "raw_heart_rate",
    "step_count": "raw_step_count"
}

app = FastAPI()

# --- 2. 适配 iOS 捷径的新缩写格式 ---
class DataItem(BaseModel):
    v: str  # value
    s: str  # start_time
    e: str  # end_time

class HealthPayload(BaseModel):
    category: str
    source: str
    unit: str
    data: List[DataItem]

# --- 3. 核心接口 ---
@app.post("/test-upload")
async def test_upload(payload: HealthPayload):
    # 动态获取表名
    table_name = TABLE_MAP.get(payload.category)
    if not table_name:
        print(f"❌ 拒绝请求: 不支持的分类 '{payload.category}'")
        raise HTTPException(status_code=400, detail=f"Unsupported category: {payload.category}")

    print(f"\n[收到推送请求] 分类: {payload.category} -> 目标表: {table_name}")
    print(f"来源: {payload.source}, 记录数: {len(payload.data)}")
    
    # 生成批次 ID (UUID)
    batch_id = str(uuid.uuid4())
    
    # 转换并清洗数据
    sql_data = []
    for item in payload.data:
        try:
            sql_data.append((
                float(item.v),   # 字符串转浮点
                payload.unit, 
                item.s,          # 开始时间
                item.e,          # 结束时间
                payload.source,
                batch_id
            ))
        except ValueError:
            print(f"⚠️ 跳过非法数值: {item.v}")

    if not sql_data:
        raise HTTPException(status_code=400, detail="No valid data points found.")

    try:
        conn = psycopg2.connect(DB_CONFIG)
        cur = conn.cursor()
        
        # 动态构造 SQL (安全地插入表名)
        query = f"""
            INSERT INTO {table_name} (value, unit, start_time, end_time, source, batch_id)
            VALUES %s
            ON CONFLICT (start_time, end_time, value, source) DO NOTHING
        """
        
        execute_values(cur, query, sql_data)
        conn.commit()
        
        inserted_count = cur.rowcount
        cur.close()
        conn.close()
        
        print(f"✅ 成功处理 {len(payload.data)} 条数据，新增入库: {inserted_count} 条，批次 ID: {batch_id}")
        return {
            "status": "success", 
            "inserted": inserted_count, 
            "batch_id": batch_id,
            "table": table_name
        }

    except Exception as e:
        print(f"❌ 数据库错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("\n🚀 API 升级版已启动！等待 iOS 捷径推送...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
