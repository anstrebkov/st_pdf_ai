import os
import streamlit as st
import google.generativeai as genai
import PyPDF2
import pikepdf
import tempfile
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])


PROMPT_TEMPLATE = """
Context from PDF document:
{context}

Question: {question}

Instructions:
1. Carefully analyze the provided context
2. Answer ONLY based on the information in the context
3. If the answer is not clearly present, respond with "I cannot find the answer in the document"
4. Be precise and concise
5. Directly reference the relevant parts of the context in your answer
"""

class PDFChatApp:
    def __init__(self):
        # Initialization of app state
        st.set_page_config(page_title="PDF Chat with AI", page_icon="📄")
        st.title("🤖 PDF Chat with AI")

        # Initialization of session states
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
        st.header("💬 Interact with Documents")

        # Check for uploaded files
        if not st.session_state.uploaded_files:
            st.warning("Please upload PDF files in the sidebar")
            return

        # Select model
        model_choice = st.selectbox(
            "Select Gemini Model",
            ["gemini-1.5-flash"]
        )

        # Save selected model in session
        st.session_state['selected_model'] = model_choice

        # Text input
        user_query = st.text_input("Enter your question about the documents")

        if st.button("Submit Request"):
            if not user_query:
                st.error("Please enter a query")
                return

            try:
                # Prepare documents for the request
                selected_gemini_files = [
                    file['gemini_file'] for file in st.session_state.uploaded_files
                ]

                if not selected_gemini_files:
                    st.error("Unable to find documents for analysis.")
                    return

                # Initialize model
                model = genai.GenerativeModel(model_choice)

                # Construct prompt content
                context = "\n\n".join([file['text'] for file in st.session_state.uploaded_files])
                prompt_content = PROMPT_TEMPLATE.format(context=context, question=user_query)

                # Generate response
                response = model.generate_content(prompt_content)

                # Display result
                st.success("🤖 Response:")
                st.write(response.text)

                # Save chat history
                st.session_state.chat_history.append({
                    'query': user_query,
                    'response': response.text
                })

            except Exception as e:
                st.error(f"Error generating response: {e}")

        # Chat history
        if st.session_state.chat_history:
            with st.expander("📜 Chat History"):
                for chat in st.session_state.chat_history:
                    st.markdown(f"**Query:** {chat['query']}")
                    st.markdown(f"**Response:** {chat['response']}")
                    st.divider()

    def run(self):
        """Main method to run the application"""
        self.process_documents()
        self.chat_interface()

# Run the application
if __name__ == "__main__":
    app = PDFChatApp()
    app.run()
