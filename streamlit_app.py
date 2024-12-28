import os
import streamlit as st
import google.generativeai as genai
import PyPDF2
import pikepdf
import tempfile
import hashlib
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

# Initialize session state
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'text_cache' not in st.session_state:
    st.session_state.text_cache = {}

# Use Streamlit's caching
@st.cache_data
def extract_text_from_pdf_cached(file_content):
    """Cached function to extract text from PDF using file content hash as cache key"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
            
            with open(temp_file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                extracted_text = ""
                for page in pdf_reader.pages:
                    try:
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n\n"
                    except Exception:
                        continue

            os.unlink(temp_file_path)
            return extracted_text if extracted_text.strip() else None
    except Exception:
        return None

@st.cache_data
def extract_text_with_pikepdf_cached(file_content):
    """Cached function to extract text using pikepdf"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
            
            pdf = pikepdf.Pdf.open(temp_file_path)
            extracted_text = ""
            for page in pdf.pages:
                try:
                    text_extraction = page.extract_text()
                    if text_extraction:
                        extracted_text += text_extraction + "\n\n"
                except Exception:
                    continue

            os.unlink(temp_file_path)
            return extracted_text if extracted_text.strip() else None
    except Exception:
        return None

class PDFChatApp:
    def __init__(self):
        st.set_page_config(page_title="Чат с PDF и AI", page_icon="📄", layout="wide")
        st.title(":books: Чат с PDF")

    def process_documents(self):
        st.sidebar.header("📤 Загрузка документов")
        
        # Clear cache button
        if st.sidebar.button("Очистить кэш"):
            st.session_state.text_cache = {}
            st.session_state.uploaded_files = []
            st.session_state.chat_history = []
            st.cache_data.clear()
            st.sidebar.success("Кэш очищен")
            return

        uploaded_files = st.sidebar.file_uploader(
            "Выберите PDF-файлы",
            type=['pdf'],
            accept_multiple_files=True,
            key="pdf_uploader"
        )

        if uploaded_files:
            with st.spinner("Обработка документов..."):
                for uploaded_file in uploaded_files:
                    file_content = uploaded_file.read()
                    
                    # Create a hash of file content for caching
                    file_hash = hashlib.md5(file_content).hexdigest()
                    
                    # Check if text is already in cache
                    if file_hash in st.session_state.text_cache:
                        extracted_text = st.session_state.text_cache[file_hash]
                    else:
                        # Try different extraction methods
                        extracted_text = extract_text_from_pdf_cached(file_content)
                        if not extracted_text:
                            extracted_text = extract_text_with_pikepdf_cached(file_content)
                        
                        if extracted_text:
                            st.session_state.text_cache[file_hash] = extracted_text

                    if extracted_text:
                        try:
                            # Create temporary file for Gemini upload
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                                temp_file.write(file_content)
                                gemini_file = genai.upload_file(temp_file.name)
                                os.unlink(temp_file.name)

                            if gemini_file:
                                # Store file info in session state
                                file_info = {
                                    'name': uploaded_file.name,
                                    'hash': file_hash,
                                    'gemini_file': gemini_file,
                                    'text': extracted_text
                                }
                                
                                # Check if file already exists in uploaded_files
                                existing_files = [f['hash'] for f in st.session_state.uploaded_files]
                                if file_hash not in existing_files:
                                    st.session_state.uploaded_files.append(file_info)
                                    st.sidebar.success(f"✅ Файл {uploaded_file.name} успешно загружен")
                                
                        except Exception as upload_error:
                            st.sidebar.error(f"Ошибка загрузки файла {uploaded_file.name}: {str(upload_error)}")
                    else:
                        st.sidebar.error(f"Не удалось извлечь текст из файла {uploaded_file.name}")

    def chat_interface(self):
        st.header("💬 Взаимодействие с документами")

        if not st.session_state.uploaded_files:
            st.warning("Пожалуйста, загрузите PDF-файлы в боковом меню")
            return

        col1, col2 = st.columns([2, 1])
        
        with col1:
            model_choice = st.selectbox(
                "Выберите модель Gemini",
                ["gemini-1.5-flash"],
                key="model_selector"
            )

            user_query = st.text_area(
                "Введите ваш вопрос к документам",
                height=100,
                key="query_input"
            )

            if st.button("Отправить запрос", key="submit_button"):
                if not user_query:
                    st.error("Пожалуйста, введите запрос")
                    return

                try:
                    with st.spinner("Генерация ответа..."):
                        model = genai.GenerativeModel(model_choice)
                        context = "\n\n".join([file['text'] for file in st.session_state.uploaded_files])
                        
                        prompt = f"""
                        Контекст из PDF-документов:
                        {context}

                        Вопрос: {user_query}

                        Инструкции:
                        1. Внимательно проанализируйте предоставленный контекст
                        2. Отвечайте ТОЛЬКО на основе информации из контекста
                        3. Если ответ не найден, укажите "Я не могу найти ответ в документе"
                        4. Будьте точными и лаконичными
                        5. Ссылайтесь на соответствующие части контекста
                        """

                        response = model.generate_content(prompt)
                        
                        st.success("🤖 Ответ:")
                        st.write(response.text)
                        
                        st.session_state.chat_history.append({
                            'query': user_query,
                            'response': response.text
                        })

                except Exception as e:
                    st.error(f"Ошибка при генерации ответа: {str(e)}")

        with col2:
            if st.session_state.chat_history:
                st.subheader("📜 История чата")
                for i, chat in enumerate(st.session_state.chat_history):
                    with st.expander(f"Диалог {i + 1}"):
                        st.markdown(f"**Вопрос:** {chat['query']}")
                        st.markdown(f"**Ответ:** {chat['response']}")

    def run(self):
        self.process_documents()
        self.chat_interface()

if __name__ == "__main__":
    app = PDFChatApp()
    app.run()
