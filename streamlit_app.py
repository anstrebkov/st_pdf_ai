import os
import streamlit as st
import google.generativeai as genai
import PyPDF2
import pikepdf
import tempfile

genai.configure(api_key="GOOGLE_API_KEY")

class PDFChatApp:
    def __init__(self):
        # Инициализация состояния приложения
        st.set_page_config(page_title="PDF Чат с AI", page_icon="📄")
        st.title("🤖 PDF Chat с  AI")

        # Инициализация сессионных состояний
        if 'uploaded_files' not in st.session_state:
            st.session_state.uploaded_files = []
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

    def extract_text_from_pdf(self, pdf_path):
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                extracted_text = ""
                for page in pdf_reader.pages:
                    try:
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n\n" # Добавляем разделитель между страницами
                    except Exception as page_error:
                        st.warning(f"Не удалось извлечь текст со страницы: {page_error}")

                # Проверяем, что текст не пустой
                if not extracted_text.strip():
                    st.error("Не удалось извлечь текст из PDF. Возможно, документ защищен или имеет сложную структуру.")
                    return None

                return extracted_text
        except Exception as e:
            st.error(f"Ошибка при чтении PDF: {e}")
            return None

    def extract_text_with_pikepdf(self, pdf_path):
        try:
            pdf = pikepdf.Pdf.open(pdf_path)
            extracted_text = ""
            for page in pdf.pages:
                try:
                    text_extraction = page.extract_text()
                    if text_extraction:
                        extracted_text += text_extraction + "\n\n"
                except Exception as page_error:
                    st.warning(f"Не удалось извлечь текст со страницы: {page_error}")

            if not extracted_text.strip():
                st.error("Не удалось извлечь текст с помощью pikepdf")
                return None

            return extracted_text
        except Exception as e:
            st.error(f"Ошибка при чтении PDF с помощью pikepdf: {e}")
            return None

    def upload_file_to_gemini(self, file_path):
        try:
            uploaded_file = genai.upload_file(file_path)
            return uploaded_file
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {e}")
            return None

    def process_documents(self):
        st.sidebar.header("📤 Загрузка документов")
        uploaded_files = st.sidebar.file_uploader(
            "Выберите PDF-файлы",
            type=['pdf'],
            accept_multiple_files=True
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(uploaded_file.getvalue())
                    temp_file_path = temp_file.name

                # Пробуем извлечь текст несколькими методами
                extracted_text = self.extract_text_from_pdf(temp_file_path)

                if not extracted_text:
                    extracted_text = self.extract_text_with_pikepdf(temp_file_path)

                if extracted_text:
                    # Загрузка в Gemini
                    try:
                        gemini_file = self.upload_file_to_gemini(temp_file_path)

                        if gemini_file:
                            st.sidebar.success(f"✅ Файл {uploaded_file.name} успешно загружен")
                            st.session_state.uploaded_files.append({
                                'name': uploaded_file.name,
                                'path': temp_file_path,
                                'gemini_file': gemini_file,
                                'text': extracted_text # Сохраняем извлеченный текст
                            })
                    except Exception as upload_error:
                        st.sidebar.error(f"Ошибка загрузки файла {uploaded_file.name}: {upload_error}")
                else:
                    st.sidebar.error(f"Не удалось извлечь текст из файла {uploaded_file.name}")

                # Удаление временного файла
                os.unlink(temp_file_path)

    def chat_interface(self):
        st.header("💬 Взаимодействие с документами")

        # Проверка наличия загруженных файлов
        if not st.session_state.uploaded_files:
            st.warning("Пожалуйста, загрузите PDF-файлы в боковом меню")
            return

        # Выбор модели
        model_choice = st.selectbox(
            "Выберите модель Gemini",
            ["gemini-1.5-flash"]
        )

        # Сохранение выбранной модели в сессии
        st.session_state['selected_model'] = model_choice

        # Текстовый ввод
        user_query = st.text_input("Введите ваш вопрос к документам")

        if st.button("Отправить запрос"):
            if not user_query:
                st.error("Введите запрос")
                return

            try:
                # Подготовка документов для запроса
                selected_gemini_files = [
                    file['gemini_file'] for file in st.session_state.uploaded_files
                ]

                if not selected_gemini_files:
                    st.error("Не удалось найти документы для анализа.")
                    return

                # Инициализация модели
                model = genai.GenerativeModel(model_choice)

                # Формирование контента для запроса
                query_content = [user_query] + selected_gemini_files

                # Генерация ответа
                response = model.generate_content(query_content)

                # Отображение результата
                st.success("🤖 Ответ :")
                st.write(response.text)

                # Сохранение истории чата
                st.session_state.chat_history.append({
                    'query': user_query,
                    'response': response.text
                })

            except Exception as e:
                st.error(f"Ошибка при генерации ответа: {e}")

        # История чата
        if st.session_state.chat_history:
            with st.expander("📜 История чата"):
                for chat in st.session_state.chat_history:
                    st.markdown(f"**Запрос:** {chat['query']}")
                    st.markdown(f"**Ответ:** {chat['response']}")
                    st.divider()

    def run(self):
        """Основной метод запуска приложения"""
        self.process_documents()
        self.chat_interface()

# Запуск приложения
if __name__ == "__main__":
    app = PDFChatApp()
    app.run()
