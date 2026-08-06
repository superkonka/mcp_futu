from fastapi import APIRouter

router = APIRouter()

@router.post("/analysis/multi_model/model")
@router.post("/analysis/multi_model/judge")
async def analysis_stub():
    return {"ret_code": 0, "data": {}}

@router.get("/fundamental/news/refresh")
async def news_stub():
    return {"ret_code": 0, "data": []}

@router.get("/recommendations")
async def recommendations_list_stub():
    return {"ret_code": 0, "data": []}

@router.get("/recommendations/{id}")
async def recommendations_detail_stub(id: str):
    return {"ret_code": 0, "data": {}}

@router.get("/recommendations/{id}/evaluations")
async def recommendations_eval_stub(id: str):
    return {"ret_code": 0, "data": []}

@router.get("/recommendations/{id}/alerts")
async def recommendations_alerts_stub(id: str):
    return {"ret_code": 0, "data": []}

@router.post("/recommendations/{id}/reevaluate")
async def recommendations_reeval_stub(id: str):
    return {"ret_code": 0, "data": {}}
