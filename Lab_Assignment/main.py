import operator
import os
from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

load_dotenv()

# ==========================================
# 1. STATE DEFINITION
# ==========================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str

# ==========================================
# 2. TOOLS
# ==========================================
@tool
def search_legal_documents(query: str) -> str:
    """Tìm kiếm tài liệu pháp luật, văn bản luật dựa trên query."""
    # Giả lập database RAG của Day 8
    query_lower = query.lower()
    if "ma tuý" in query_lower:
        return "[Luật Phòng chống ma tuý 2021, Điều 3] Các hành vi bị nghiêm cấm bao gồm tàng trữ, vận chuyển trái phép chất ma tuý."
    elif "lao động" in query_lower:
        return "[Bộ luật Lao động 2019, Điều 104] Thời gian làm việc bình thường không quá 08 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần."
    elif "án lệ" in query_lower:
        return "[Án lệ số 01/2016/AL] Về vụ án giết người."
    return "Không tìm thấy tài liệu phù hợp trong hệ thống."

# ==========================================
# 3. WORKER NODES
# ==========================================
# Khởi tạo LLM (Cấu hình OpenRouter hoặc OpenAI từ .env)
# Mặc định sử dụng gpt-4o-mini hoặc model chỉ định trong .env
llm = ChatOpenAI(
    model=os.getenv("OPENROUTER_MODEL", "gpt-4o-mini"),
    temperature=0.2
)

def make_agent_node(agent, name: str):
    def node(state: AgentState):
        result = agent.invoke({"messages": state["messages"]})
        # Lấy tin nhắn cuối cùng trả về từ agent và gán name của worker
        last_msg = result["messages"][-1]
        return {"messages": [AIMessage(content=last_msg.content, name=name)]}
    return node

# -- Worker 1: Researcher --
researcher_agent = create_react_agent(
    llm, 
    [search_legal_documents], 
    state_modifier="Bạn là một Legal Researcher. Nhiệm vụ của bạn là dùng tool 'search_legal_documents' để tìm kiếm các văn bản luật liên quan đến câu hỏi. Luôn luôn trả về trích dẫn nguyên văn."
)
researcher_node = make_agent_node(researcher_agent, "Researcher")

# -- Worker 2: Drafter --
drafter_agent = create_react_agent(
    llm, 
    [], 
    state_modifier="Bạn là một Legal Drafter. Nhiệm vụ của bạn là viết câu trả lời cho người dùng dựa trên thông tin mà Researcher cung cấp. Bắt buộc phải có trích dẫn ([Nguồn]) cho mọi thông tin pháp lý đưa ra."
)
drafter_node = make_agent_node(drafter_agent, "Drafter")

# -- Worker 3: Reviewer --
reviewer_agent = create_react_agent(
    llm, 
    [], 
    state_modifier="Bạn là một Legal Reviewer. Nhiệm vụ của bạn là kiểm tra xem Drafter đã trả lời đúng chưa và có trích dẫn nguồn đầy đủ hay không. Nếu bản nháp đã tốt, hãy phản hồi bắt đầu bằng chữ 'LOOKS GOOD'. Nếu chưa, hãy chỉ ra điểm cần sửa để Drafter viết lại."
)
reviewer_node = make_agent_node(reviewer_agent, "Reviewer")


# ==========================================
# 4. SUPERVISOR NODE
# ==========================================
members = ["Researcher", "Drafter", "Reviewer"]
options = members + ["FINISH"]

class RouteResponse(BaseModel):
    next: str = Field(description="Worker tiếp theo cần thực thi, hoặc 'FINISH' nếu đã hoàn thành.")

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", "Bạn là một Supervisor quản lý các worker sau: {members}.\n\n"
               "Dựa trên yêu cầu của người dùng và lịch sử chat, hãy chỉ định worker nào cần làm việc tiếp theo.\n"
               "- Nếu chưa có thông tin tra cứu, chọn 'Researcher'.\n"
               "- Nếu Researcher đã tìm ra thông tin, chọn 'Drafter' để soạn thảo.\n"
               "- Nếu Drafter đã soạn thảo xong, chọn 'Reviewer' để kiểm tra.\n"
               "- Nếu Reviewer duyệt và nói 'LOOKS GOOD', hãy chọn 'FINISH'.\n\n"
               "Chỉ trả về tên worker kế tiếp hoặc 'FINISH'."),
    MessagesPlaceholder(variable_name="messages"),
    ("system", "Dựa trên hội thoại trên, worker nào nên chạy tiếp theo? Chọn 1 trong số: {options}")
])

supervisor_chain = supervisor_prompt | llm.with_structured_output(RouteResponse)

def supervisor_node(state: AgentState):
    routing = supervisor_chain.invoke({
        "messages": state["messages"],
        "members": ", ".join(members),
        "options": ", ".join(options)
    })
    return {"next": routing.next}


# ==========================================
# 5. BUILD GRAPH
# ==========================================
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("Researcher", researcher_node)
workflow.add_node("Drafter", drafter_node)
workflow.add_node("Reviewer", reviewer_node)
workflow.add_node("supervisor", supervisor_node)

# Các worker sau khi xong việc sẽ quay lại báo cáo cho supervisor
for member in members:
    workflow.add_edge(member, "supervisor")

# Supervisor quyết định route đi đâu
conditional_map = {k: k for k in members}
conditional_map["FINISH"] = END

workflow.add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)

# Entry point
workflow.add_edge(START, "supervisor")

graph = workflow.compile()

# ==========================================
# 6. EXECUTION SCRIPT
# ==========================================
if __name__ == "__main__":
    print("="*50)
    print("🤖 Legal Supervisor Multi-Agent System (Day 9)")
    print("="*50)
    
    question = "Thời gian làm việc một tuần tối đa là bao nhiêu giờ theo luật lao động?"
    print(f"\nUser Query: {question}\n")
    
    initial_state = {"messages": [HumanMessage(content=question)]}
    
    for s in graph.stream(initial_state, {"recursion_limit": 20}):
        if "__end__" not in s:
            # s is a dict mapping node_name -> state update
            node_name = list(s.keys())[0]
            print(f"\n--- Output from {node_name} ---")
            if "messages" in s[node_name]:
                print(s[node_name]["messages"][-1].content)
            elif "next" in s[node_name]:
                print(f"Supervisor routing to: {s[node_name]['next']}")
            print("-" * 30)
