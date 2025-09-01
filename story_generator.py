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

# カテゴリ分類の辞書
CATEGORY_MAPPING = {
    "古典神話・宗教": ["古事記", "聖書", "北欧神話", "ギリシャ神話", "エジプト神話", "メソポタミア神話", "ゲルマン神話", "ケルト"],
    "民話・説話": ["アラブ系文学", "インド系文学", "イソップ", "グリム", "日本昔話", "アジア古典", "日本の古典文学"],
    "古典・近世文学": ["世界演劇", "世界文学"],
    "現代・都市伝説": ["近現代の映画・小説", "都市伝説・現代民話"]
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
        if char.isalnum() or char in "ーあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽァィゥェォッャュョアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ一二三四五六七八九十百千万億兆":
            safe_title += char
        elif char in " 　":
            safe_title += "_"
    
    # 空の場合はデフォルト名を使用
    if not safe_title.strip():
        safe_title = "generated_story"
    
    # 最大長を30文字に制限
    if len(safe_title) > 30:
        safe_title = safe_title[:30]
    
    # ファイル名を作成（日付_題名.txt）
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}_{safe_title}.txt"
    
    # Streamlitのダウンロードボタンを作成
    return st.download_button(
        label="💾 物語をダウンロード",
        data=story,
        file_name=filename,
        mime="text/plain",
        use_container_width=True,
        help=f"物語を '{filename}' としてダウンロード"
    )

def main():
    st.title("📚 古典融合ストーリーメーカー")
    st.markdown("古典の要素を融合して、新しい物語を創造します")
    
    # データの読み込み
    story_data = load_story_elements()
    if story_data is None:
        st.stop()
    
    # サイドバーで設定
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # カテゴリ選択
        st.subheader("📚 使用するジャンル")
        use_mythology = st.checkbox("古典神話・宗教", value=True, 
                                   help="古事記、聖書、北欧神話、ギリシャ神話、エジプト神話、メソポタミア神話、ゲルマン神話、ケルト")
        use_folktales = st.checkbox("民話・説話", value=True,
                                   help="アラブ系文学、インド系文学、イソップ、グリム、日本昔話、アジア古典、日本の古典文学")
        use_classical = st.checkbox("古典・近世文学", value=True,
                                   help="世界演劇、世界文学")
        use_modern = st.checkbox("現代・都市伝説", value=True,
                                help="近現代の映画・小説、都市伝説・現代民話")
        
        # 選択されたカテゴリを取得
        selected_categories = []
        if use_mythology:
            selected_categories.append("古典神話・宗教")
        if use_folktales:
            selected_categories.append("民話・説話")
        if use_classical:
            selected_categories.append("古典・近世文学")
        if use_modern:
            selected_categories.append("現代・都市伝説")
        
        # フィルタリングされたデータを取得
        filtered_story_data = get_filtered_story_data(story_data, selected_categories)
        
        if not filtered_story_data:
            st.warning("少なくとも1つのカテゴリを選択してください。")
            st.stop()
        
        st.divider()
        
        # デバッグモード（開発用）
        debug_mode = st.checkbox("🔍 デバッグモード", value=False)
        
        # 文字数設定
        word_count = st.number_input(
            "仕上がり文字数",
            min_value=100,
            max_value=2000,
            value=600,
            step=100
        )
        
        # 使用する物語要素数
        total_elements = sum(len(elements) for elements in filtered_story_data.values())
        num_elements = st.number_input(
            "使用する物語要素の数",
            min_value=1,
            max_value=min(10, total_elements),
            value=2,
            step=1
        )
        
        if debug_mode:
            st.subheader("📊 データ統計")
            st.write(f"総要素数: {total_elements}")
            st.write("選択されたカテゴリ:")
            for category in selected_categories:
                st.write(f"- {category}")
            st.write("含まれるジャンル:")
            for collection, elements in filtered_story_data.items():
                st.write(f"- {collection}: {len(elements)}要素")
        
        # 自由入力
        custom_text = st.text_area(
            "自由入力（プロンプトに追加する指示）",
            value="",
            height=120
        )
        
        # 出力設定
        output_mode = st.radio(
            "出力設定",
            ["プロンプトのみ出力", "本文まで生成"]
        )
        
        # API key入力（本文生成の場合のみ）
        api_key = ""
        if output_mode == "本文まで生成":
            api_key = st.text_input(
                "Claude API Key",
                type="password",
                help="https://console.anthropic.com でAPIキーを取得してください"
            )
    
    # メインエリア
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("🎲 物語要素選択")
        
        if st.button("要素をランダム選択", type="primary"):
            selected_elements = select_random_elements(filtered_story_data, num_elements)
            if selected_elements:
                st.session_state.selected_elements = selected_elements
                
                # 選択履歴を記録（デバッグ用）
                if 'selection_history' not in st.session_state:
                    st.session_state.selection_history = []
                
                # 各要素の名前を履歴に追加
                for element in selected_elements:
                    element_name = f"{element['collection']} - {element['story_name']}"
                    st.session_state.selection_history.append(element_name)
                
                # 履歴が長くなりすぎないように制限
                if len(st.session_state.selection_history) > 100:
                    st.session_state.selection_history = st.session_state.selection_history[-100:]
        
        # 選択された要素を表示
        if 'selected_elements' in st.session_state:
            st.subheader("選択された要素:")
            for i, element in enumerate(st.session_state.selected_elements, 1):
                # 古い形式のデータ構造
                with st.expander(f"{i}. {element['collection']} - {element['story_name']}"):
                    st.write(f"**要素:** {element['element']}")
        
        # デバッグモード時の選択履歴表示
        if debug_mode and 'selection_history' in st.session_state:
            st.subheader("🔍 選択履歴（最近20回）")
            recent_history = st.session_state.selection_history[-20:]
            
            # 頻度カウント
            from collections import Counter
            frequency = Counter(recent_history)
            
            st.write("**最近選択された要素の頻度:**")
            for element, count in frequency.most_common(10):
                percentage = (count / len(recent_history)) * 100
                st.write(f"- {element}: {count}回 ({percentage:.1f}%)")
            
            if st.button("選択履歴をクリア"):
                st.session_state.selection_history = []
                st.rerun()
        
        # プロンプト生成
        if 'selected_elements' in st.session_state:
            prompt = create_prompt(st.session_state.selected_elements, word_count, custom_text)
            st.session_state.current_prompt = prompt
            
            st.subheader("📝 生成されたプロンプト:")
            st.text_area("プロンプト", value=prompt, height=200, key="prompt_display")
    
    with col2:
        st.header("📖 物語生成")
        
        # プロンプトのみの場合
        if output_mode == "プロンプトのみ出力":
            if 'current_prompt' in st.session_state:
                st.success("プロンプトが生成されました！左側のテキストエリアからコピーしてお使いください。")
                
                # プロンプトのダウンロードボタンも追加
                st.download_button(
                    label="📥 プロンプトをダウンロード",
                    data=st.session_state.current_prompt,
                    file_name=f"story_prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
        
        # 本文生成の場合
        elif output_mode == "本文まで生成":
            if not api_key:
                st.warning("Claude API Keyを入力してください。")
            elif 'current_prompt' in st.session_state:
                if st.button("物語を生成", type="primary"):
                    # プロンプトの内容をデバッグ表示（本番では非表示にできます）
                    if debug_mode:
                        with st.expander("🐛 デバッグ情報（プロンプト内容確認）"):
                            st.text(f"プロンプトの長さ: {len(st.session_state.current_prompt)} 文字")
                            st.text("プロンプトの最初の200文字:")
                            st.text(st.session_state.current_prompt[:200] + "..." if len(st.session_state.current_prompt) > 200 else st.session_state.current_prompt)
                            
                            # 問題のある文字をチェック
                            try:
                                st.session_state.current_prompt.encode('ascii')
                                st.success("プロンプトにASCII以外の文字は含まれていません")
                            except UnicodeEncodeError as e:
                                st.warning(f"プロンプトにASCII以外の文字が含まれています: 位置 {e.start}-{e.end}")
                                st.text(f"問題の文字: '{st.session_state.current_prompt[e.start:e.end+1]}'")
                                st.info("これは正常です。日本語を使用しているためです。Claude APIは日本語に対応しています。")
                    
                    with st.spinner("物語を生成中..."):
                        story = generate_story_with_claude(st.session_state.current_prompt, api_key)
                        st.session_state.generated_story = story
                
                # 生成された物語を表示
                if 'generated_story' in st.session_state:
                    st.subheader("✨ 生成された物語:")
                    st.write(st.session_state.generated_story)
                    
                    # 物語から題名を自動抽出
                    auto_title = extract_title_from_story(st.session_state.generated_story)
                    
                    # 修正された保存機能
                    col_save1, col_save2 = st.columns([2, 1])
                    with col_save1:
                        # 自動抽出された題名をデフォルトに設定
                        save_title = st.text_input(
                            "保存時のファイル名（日付_題名.txt形式）", 
                            value=auto_title,
                            help="物語の最初の行から自動抽出された題名です。編集可能です。"
                        )
                    with col_save2:
                        # 修正：Streamlitのダウンロードボタンを使用
                        if create_download_button(st.session_state.generated_story, save_title):
                            st.success("ダウンロードが開始されました！")
    
    # フッター
    st.markdown("---")
    st.markdown("**使用方法:**")
    st.markdown("""
    1. サイドバーで使用するジャンルカテゴリを選択
    2. 文字数、要素数、追加指示を設定
    3. 「要素をランダム選択」ボタンをクリック
    4. プロンプトのみ必要な場合は、生成されたプロンプトをコピー
    5. 物語まで生成する場合は、API Keyを入力して「物語を生成」をクリック
    6. 気に入った物語は保存ボタンで保存可能
    """)

if __name__ == "__main__":
    main()
