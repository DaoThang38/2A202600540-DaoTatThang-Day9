# Giải quyết các bài Lab trên lớp - Codelab: Xây Dựng Hệ Thống Multi-Agent

## Phần 1: Direct LLM Calling
**Bài Tập 1.1: Thay đổi câu hỏi**
Sửa biến `QUESTION` trong file `main.py`:
```python
QUESTION = "Thời gian làm việc tối đa một tuần theo luật lao động Việt Nam là bao nhiêu?"
```

**Bài Tập 1.2: Thêm temperature control**
Sửa trong `common/llm.py` (nếu có) hoặc lúc khởi tạo LLM:
```python
llm = ChatOpenAI(temperature=0.3, model=os.getenv("OPENROUTER_MODEL"))
```

## Phần 2: LLM + RAG & Tools
**Bài Tập 2.1: Thêm knowledge base entry**
Thêm dict vào mảng `LEGAL_KNOWLEDGE`:
```python
{
    "id": "labor_law",
    "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination"],
    "text": (
        "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
        "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
        "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
        "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu."
    ),
}
```

**Bài Tập 2.2: Tạo tool mới**
Tạo tool `check_statute_of_limitations` bằng decorator `@tool` như mô tả trong đề và thêm vào danh sách tools truyền vào `.bind_tools(tools)`.

## Phần 3: Single Agent với ReAct
**Bài Tập 3.1: Thêm tool tra cứu án lệ**
Khai báo tool `search_case_law` tương tự như đề và truyền mảng tools `[..., search_case_law]` cho logic khởi tạo `create_react_agent`.
**Bài Tập 3.2: Debug agent reasoning**
Sửa tham số khi gọi agent logic để bật log: `create_react_agent(llm, tools, debug=True)` hoặc thêm `verbose=True` tùy version lib LangGraph.

## Phần 4: Multi-Agent In-Process
**Bài Tập 4.1: Thêm agent mới**
Tạo hàm `privacy_agent(state: State) -> dict` như đề cập, sau đó gọi `graph.add_node("privacy_agent", privacy_agent)` và add edge từ `privacy_agent` tới node kết xuất / aggregate.
**Bài Tập 4.2: Implement conditional routing**
Thêm keyword check vào `check_routing`, append `Send("privacy_agent", state)` nếu chứa các từ khóa như "data", "privacy", "gdpr", "dữ liệu".

## Phần 5: Distributed A2A System
**Bài Tập 5.1: Trace request flow**
Flow: Customer Agent (nhận query) -> Tìm Law Agent qua Registry -> Law Agent xử lý & gửi request song song tới Tax Agent và Compliance Agent -> Trả về kết quả cho Customer Agent thông qua aggregation.
**Bài Tập 5.2: Test dynamic discovery**
Khi dừng Tax Agent, Registry không kết nối được tới Tax Agent. Agent Orchestrator có thể sẽ ném ra timeout hoặc trả về error message trong block của Tax Agent.
**Bài Tập 5.3: Modify agent behavior**
Thêm chỉ thị "Hãy trả lời thật ngắn gọn, dưới 50 chữ." vào system prompt trong `tax_agent/graph.py` và restart.

## Phần 6: Câu hỏi ôn tập & Bài Tập Cộng Điểm
**Câu 1:** Khi nào nên dùng single agent thay vì multi-agent?
-> Khi task đơn giản, quy trình tuần tự rõ ràng, domain hẹp, giúp giảm latency và tiết kiệm token/overhead quản lý.
**Câu 2:** Ưu điểm A2A so với gRPC/REST?
-> Hỗ trợ dynamic discovery qua Registry, agent có thể auto-register, giảm hardcode. Chuẩn hóa interface cho agent interaction.
**Câu 3:** Làm thế nào prevent infinite delegation loops?
-> Tracking qua depth (vd `MAX_DELEGATION_DEPTH=3`) và duy trì context/trace_id trong message metadata để detect loop.
**Câu 4:** Tại sao cần Registry service?
-> Để các agents có service discovery ở runtime, giúp scale linh hoạt (thêm bớt node) mà không cần cấu hình tĩnh.

**Bài Tập Cộng Điểm:**
- **Latency trung bình:** Phụ thuộc mạng và API LLM, dao động 10-20s cho một lượt RTT.
- **Phương án giảm latency:**
  1. Dùng model nhỏ/nhanh (`gemini-2.0-flash` hoặc Claude Haiku) cho bước routing/intent detection.
  2. Bật LLM Streaming output cho FE.
  3. Bỏ bớt bước phân rã không cần thiết với simple query.
