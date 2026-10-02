import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import streamlit as st

# 테스트할 때는 환경변수로 다른 파일을 지정할 수 있음
DATA_FILE = Path(os.environ.get("SHOPPING_LIST_FILE", Path(__file__).with_name("shopping_list.json")))
MAX_LEN = 100


@st.cache_resource
def file_lock():
    # 여러 탭(세션)이 동시에 파일을 고칠 때 서로 덮어쓰지 않도록 하는 잠금
    return threading.Lock()


st.set_page_config(page_title="나의 쇼핑리스트", page_icon="🛒", layout="centered")


# ---------- 저장/불러오기 ----------

def load_items():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    # 손상되었거나 형식이 맞지 않는 항목은 건너뜀
    items = []
    for i in data:
        if not isinstance(i, dict) or not isinstance(i.get("name"), str) or not i["name"].strip():
            continue
        items.append({
            "id": i["id"] if isinstance(i.get("id"), str) and i["id"] else str(uuid.uuid4()),
            "name": i["name"].strip(),
            "checked": i.get("checked") is True,
            "createdAt": i["createdAt"] if isinstance(i.get("createdAt"), (int, float)) else int(time.time() * 1000),
        })
    return items


def save_items(items):
    # 임시 파일에 쓴 뒤 교체해서, 저장 중에 멈춰도 파일이 깨지지 않게 함
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)


def modify_items(change):
    # 항상 파일의 최신 내용을 읽어서 고친 뒤 저장 (다른 탭의 변경을 덮어쓰지 않음)
    with file_lock():
        items = load_items()
        change(items)
        save_items(items)


def find_item(items, item_id):
    return next((i for i in items if i["id"] == item_id), None)


def escape_md(text):
    # 사용자 입력이 마크다운/HTML/링크로 해석되지 않도록 모든 ASCII 특수문자 이스케이프
    return re.sub(r"([!-/:-@\[-`{-~])", r"\\\1", text)


# ---------- 상태 초기화 ----------

st.session_state.setdefault("editing_id", None)
st.session_state.setdefault("add_error", False)
st.session_state.setdefault("edit_error", False)


# ---------- 콜백 ----------

def add_item():
    name = st.session_state.new_item.strip()
    st.session_state.new_item = ""
    if not name:
        st.session_state.add_error = True
        return
    st.session_state.add_error = False
    modify_items(lambda items: items.append({
        "id": str(uuid.uuid4()),
        "name": name,
        "checked": False,
        "createdAt": int(time.time() * 1000),
    }))


def toggle_item(item_id):
    checked = st.session_state[f"chk_{item_id}"]

    def change(items):
        item = find_item(items, item_id)
        if item:
            item["checked"] = checked

    modify_items(change)


def start_edit(item_id):
    item = find_item(load_items(), item_id)
    if item:
        st.session_state.editing_id = item_id
        st.session_state.edit_error = False
        st.session_state[f"edit_{item_id}"] = item["name"]


def save_edit(item_id):
    name = st.session_state.get(f"edit_{item_id}", "").strip()
    if not name:
        st.session_state.edit_error = True
        return

    def change(items):
        item = find_item(items, item_id)
        if item:
            item["name"] = name

    modify_items(change)
    st.session_state.edit_error = False
    st.session_state.editing_id = None


def cancel_edit():
    st.session_state.edit_error = False
    st.session_state.editing_id = None


def delete_item(item_id):
    modify_items(lambda items: items.__setitem__(slice(None), [i for i in items if i["id"] != item_id]))
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None


@st.dialog("아이템 삭제")
def confirm_delete(item_id):
    item = find_item(load_items(), item_id)
    if not item:
        st.rerun()
    st.text(f"'{item['name']}'을(를) 삭제할까요?")
    c1, c2 = st.columns(2)
    if c1.button("삭제", type="primary", use_container_width=True):
        delete_item(item_id)
        st.rerun()
    if c2.button("취소", use_container_width=True):
        st.rerun()


# ---------- 스타일 ----------

st.markdown(
    """
    <style>
      .block-container { max-width: 560px; padding-top: 2rem; }
      h1 { text-align: center; }
      .summary { text-align: center; color: #5b6472; margin-top: 1rem; }
      .empty { text-align: center; color: #7a8494; padding: 1.5rem 0; }
      div[data-testid="stHorizontalBlock"] { align-items: center; flex-wrap: nowrap !important; gap: 0.5rem; }
      /* 좁은 화면(모바일)에서도 체크박스·이름·버튼이 한 줄에 놓이도록 */
      div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { min-width: 0 !important; }
      div[data-testid="stColumn"] button { padding-left: 0.4rem; padding-right: 0.4rem; white-space: nowrap; min-height: 44px; }
      div[data-testid="stColumn"] [data-testid="stMarkdownContainer"] p { overflow-wrap: anywhere; margin: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- 화면 ----------

st.title("🛒 나의 쇼핑리스트")

with st.form("add_form", clear_on_submit=False, border=False):
    c1, c2 = st.columns([5, 1])
    c1.text_input("아이템 이름", key="new_item", placeholder="아이템 이름 입력...",
                  max_chars=MAX_LEN, label_visibility="collapsed")
    c2.form_submit_button("추가", type="primary", use_container_width=True, on_click=add_item)

if st.session_state.add_error:
    st.caption("⚠️ 아이템 이름을 입력해 주세요.")

# 화면을 그릴 때마다 파일에서 최신 목록을 읽음 (다른 탭에서 바꾼 내용도 반영)
items = load_items()
if st.session_state.editing_id and not find_item(items, st.session_state.editing_id):
    st.session_state.editing_id = None

if not items:
    st.markdown('<p class="empty">쇼핑 목록이 비어 있어요. 아이템을 추가해 보세요!</p>', unsafe_allow_html=True)
else:
    with st.container(border=True):
        for item in items:
            iid = item["id"]
            if st.session_state.editing_id == iid:
                # 수정 모드: 폼이라 Enter로 저장 가능
                with st.form(f"edit_form_{iid}", border=False):
                    c1, c2, c3 = st.columns([4, 1, 1])
                    c1.text_input("아이템 이름 수정", key=f"edit_{iid}", max_chars=MAX_LEN,
                                  label_visibility="collapsed")
                    c2.form_submit_button("저장", type="primary", use_container_width=True,
                                          on_click=save_edit, args=(iid,))
                    c3.form_submit_button("취소", use_container_width=True, on_click=cancel_edit)
                if st.session_state.edit_error:
                    st.caption("⚠️ 빈 이름으로는 저장할 수 없어요.")
            else:
                # 체크 상태는 항상 파일 기준으로 맞춤
                st.session_state[f"chk_{iid}"] = item["checked"]
                c0, c1, c2, c3 = st.columns([0.6, 4, 1, 1])
                c0.checkbox(f"{item['name']} 구매 완료", key=f"chk_{iid}",
                            on_change=toggle_item, args=(iid,), label_visibility="collapsed")
                name = escape_md(item["name"])
                c1.markdown(f":gray[~~{name}~~]" if item["checked"] else name)
                c2.button("수정", key=f"editbtn_{iid}", use_container_width=True,
                          on_click=start_edit, args=(iid,))
                if c3.button("삭제", key=f"delbtn_{iid}", use_container_width=True):
                    confirm_delete(iid)

    done = sum(1 for i in items if i["checked"])
    st.markdown(f'<p class="summary">전체 {len(items)}개 / 완료 {done}개</p>', unsafe_allow_html=True)
