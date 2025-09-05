import streamlit as st
import json
import random
import os
import sys
from datetime import datetime
import anthropic
import time

# 文字エンコーディングの設定
if hasattr(sys, 'set_int_max_str_digits'):
    sys.set_int_max_str_digits(10000)

# 環境変数でUTF-8を強制
os.environ['PYTHONIOENCODING'] = 'utf-8'

# ページ設定
st.set_page_config(
    page_title="古典融合ストーリーメーカー",
    page_icon="📚",
    layout="wide"
)

# カテゴリ分類の辞書 - チェックボックスのラベルとJSONのキーをマッピング
CATEGORY_MAPPING = {
    "日本の神話": ["古事記", "日本昔話", "日本の古典文学"],
    "世界の神話": ["聖書", "北欧神話", "ギリシャ神話", "エジプト神話", "メソポタミア神話", "ゲルマン神話", "アラブ系文学", "インド系文学", "ケルト", "アジア古典"],
    "昔話": ["イソップ", "グリム"],
    "演劇": ["世界演劇", "世界文学"],
    "エンタメ": ["映画", "都市伝説", "ラノベ"]
}

def load_story_elements():
    """story_elements.jsonを読み込む"""
    try:
        with open('story_elements.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("story_elements.jsonが見つかりません。先にデータ変換を実行してください。")
        return None

def get_filtered_story_data(story_data, selected_categories):
    """選択されたカテゴリのジャンルのみを含むデータを返す"""
    if not selected_categories:
        st.warning("少なくとも1つのカテゴリを選択してください。")
        return {}
    
    # 選択されたカテゴリに含まれるジャンル名を取得
    selected_genres = []
    for category in selected_categories:
        if category in CATEGORY_MAPPING:
            selected_genres.extend(CATEGORY_MAPPING[category])
    
    # フィルタリングされたデータを作成
    filtered_data = {}
    for genre_name, elements in story_data.items():
        if genre_name in selected_genres:
            filtered_data[genre_name] = elements
    
    return filtered_data

def select_random_elements(story_data, num_elements):
    """ランダムに物語要素を選択する"""
    all_elements = []
    
    # 古い形式のJSONに対応（collection -> elements）
    for collection_name, elements in story_data.items():
        for element in elements:
            all_elements.append({
                'collection': collection_name,
                'story_name': element['story_name'],
                'element': element['element']
            })
    
    if not all_elements:
        st.error("選択されたカテゴリに物語要素が見つかりません。")
        return []
    
    # ランダムに選択（真のランダムを保証）
    import time
    random.seed(time.time())  # 現在時刻をシードに使用
    selected = random.sample(all_elements, min(num_elements, len(all_elements)))
    
    return selected

def create_prompt(selected_elements, word_count, custom_text=""):
    """生成AIに送るプロンプトを作成"""
    try:
        prompt = f"以下の物語の要素を包含して、ストーリーを作ってください。文字数は{word_count}文字前後です。出典から個人名や地名などの固有名詞を引用せず、キャッチーで覚えやすい名前にしてください。最後に、古典名と内容を載せてください。\n\n"
        
        for i, element in enumerate(selected_elements, 1):
            # 古い形式のデータ構造
            collection = element['collection']
            story_name = element['story_name']
            element_text = element['element']
            
            prompt += f"{collection}の、{story_name} - 「{element_text}」\n"
        
        if custom_text.strip():
            prompt += f"\n追加指示: {custom_text.strip()}\n"
        
        return prompt
        
    except Exception as e:
        st.error(f"プロンプト作成時にエラー: {str(e)}")
        return "エラーが発生したため、プロンプトを作成できませんでした。"

def generate_story_with_claude(prompt, api_key):
    """Claude APIを使って物語を生成"""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        return message.content[0].text
        
    except Exception as e:
        error_msg = str(e)
        if "ascii" in error_msg.lower():
            st.error("文字エンコーディングの問題が発生しました。")
            st.error("これはシステムの設定に関する問題の可能性があります。")
            
            # 簡単な解決策を提案
            st.info("解決策:")
            st.info("1. コマンドプロンプトで以下を実行してから再度お試しください:")
            st.code("set PYTHONIOENCODING=utf-8")
            st.info("2. または、プロンプトをコピーして他のClaude環境で使用してください。")
            
        return f"エラーが発生しました: {error_msg}"

def extract_title_from_story(story):
    """物語の最初の行から題名を抽出"""
    if not story:
        return "generated_story"
    
    lines = story.strip().split('\n')
    if not lines:
        return "generated_story"
    
    # 最初の行を取得
    first_line = lines[0].strip()
    
    # 空行の場合は次の行を探す
    for line in lines:
        line = line.strip()
        if line:
            first_line = line
            break
    
    # ファイル名に使えない文字を除去・置換
    title = first_line.replace('/', '_').replace('\\', '_').replace(':', '_')
    title = title.replace('*', '_').replace('?', '_').replace('"', '_')
    title = title.replace('<', '_').replace('>', '_').replace('|', '_')
    
    # 長すぎる場合は切り詰める
    if len(title) > 50:
        title = title[:50]
    
    return title if title else "generated_story"

def create_download_button(story, title):
    """Streamlitのダウンロード機能でファイル保存"""
    # 安全なファイル名の作成
    safe_title = ""
    for char in title:
        if char.isalnum() or char in "ーあいうえおかきくけこさしすせそたちつてとなにぬねの
