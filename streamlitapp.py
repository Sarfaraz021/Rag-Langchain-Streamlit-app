import os
import time  # Add this import statement
import streamlit as st
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts.prompt import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import Docx2txtLoader, UnstructuredExcelLoader, CSVLoader, TextLoader, PyPDFLoader
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from prompt import template


class RAGAssistant:
    def __init__(self):
        self.load_env_variables()
        self.setup_prompt_template()
        self.relative_path = 'templates'
        self.filename = 'demo.txt'
        self.absolute_path = os.path.join(self.relative_path, self.filename)
        self.retriever = None
        self.initialize_retriever(self.absolute_path)
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.9)

    def load_env_variables(self):
        load_dotenv('var.env')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

    def setup_prompt_template(self):
        self.prompt_template = PromptTemplate(
            input_variables=["history", "context", "question"],
            template=template,
        )

    def initialize_retriever(self, directory_path):
        loader = TextLoader(directory_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)
        embeddings = OpenAIEmbeddings()
        Pinecone(api_key=self.pinecone_api_key, environment='gcp-starter')
        vectbd = PineconeVectorStore.from_documents(
            docs, embeddings, index_name=self.pinecone_index_name)
        self.retriever = vectbd.as_retriever()

    def finetune(self, file_path):
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.txt'):
            loader = TextLoader(file_path)
        elif file_path.endswith('.csv'):
            loader = CSVLoader(file_path=file_path)
        elif file_path.endswith('.xlsx'):
            loader = UnstructuredExcelLoader(file_path, mode="elements")
        elif file_path.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        else:
            raise ValueError("Unsupported file type.")

        documents = loader.load_and_split() if hasattr(
            loader, 'load_and_split') else loader.load()
        self.process_documents(documents)
        os.remove(file_path)  # Remove the file after processing

    def process_documents(self, documents):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)
        embeddings = OpenAIEmbeddings()
        Pinecone(api_key=self.pinecone_api_key, environment='gcp-starter')
        vectbd = PineconeVectorStore.from_documents(
            docs, embeddings, index_name=self.pinecone_index_name)
        self.retriever = vectbd.as_retriever()

    def chat(self, user_input):
        chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type='stuff',
            retriever=self.retriever,
            chain_type_kwargs={"verbose": False, "prompt": self.prompt_template,
                               "memory": ConversationBufferMemory(memory_key="history", input_key="question")}
        )
        assistant_response = chain.invoke(user_input)
        response_text = assistant_response['result']

        def response_generator(response_text):
            for word in response_text.split():
                yield word + " "
                time.sleep(0.05)  # Adjust delay as needed

        return response_generator(response_text)


rag_assistant = RAGAssistant()

st.set_page_config(page_title="RAG Assistant", layout="wide")

st.title("RAG Assistant")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

option = st.sidebar.selectbox("Choose an option", ("Chat", "Fine-tuning"))

if option == "Chat":
    st.header("Chat with RAG Assistant")


elif option == "Fine-tuning":
    st.header("Fine-tune RAG Assistant")
    uploaded_file = st.file_uploader(
        "Upload a file for fine-tuning", type=["txt", "pdf", "csv", "xlsx", "docx"])

    if uploaded_file is not None:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with st.spinner("Fine-tuning in progress..."):
            rag_assistant.finetune(file_path)
        st.success(
            "Fine-tuning done successfully. You can now chat with the updated RAG Assistant.")