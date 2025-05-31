from langchain_ollama import OllamaEmbeddings
from langchain_ollama.llms import OllamaLLM
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
import os
import pandas as pd
import json
import PyPDF2
import xlrd

# Initialize embeddings and model
embeddings = OllamaEmbeddings(model="mxbai-embed-large")
model = OllamaLLM(model="llama3.2")


# Load documents from multiple sources
def load_documents(folder_path="/Users/mac/Downloads/data"):
    """
    Load documents from various sources (CSV, PDF, Excel, etc.)

    Args:
        folder_path (str): Path to the folder containing documents.
                          If None, uses current directory.
    """
    documents = []
    ids = []
    doc_counter = 0
    total_docs_added = 0

    # Set the directory to search for documents
    if folder_path is None:
        search_directory = '.'
        print("Loading documents from current directory...")
    else:
        search_directory = folder_path
        print(f"Loading documents from: {folder_path}")

        # Check if the folder exists
        if not os.path.exists(folder_path):
            print(f"Error: Folder '{folder_path}' does not exist.")
            return [], []

        if not os.path.isdir(folder_path):
            print(f"Error: '{folder_path}' is not a directory.")
            return [], []

    try:
        # Get all files in the directory
        all_files = os.listdir(search_directory)
    except PermissionError:
        print(f"Error: Permission denied to access '{search_directory}'")
        return [], []
    except Exception as e:
        print(f"Error accessing directory '{search_directory}': {e}")
        return [], []

    # Load CSV files
    csv_files = [f for f in all_files if f.endswith('.csv')]
    print(f"Found {len(csv_files)} CSV files")

    for csv_file in csv_files:
        if total_docs_added >= MAX_TOTAL_DOCUMENTS:
            print(f"Reached maximum document limit ({MAX_TOTAL_DOCUMENTS})")
            break

        csv_path = os.path.join(search_directory, csv_file)
        try:
            df = pd.read_csv(csv_path)
            print(f"  Loading CSV: {csv_file} ({len(df)} rows)")

            # Limit rows per file
            rows_to_process = min(len(df), MAX_DOCUMENTS_PER_FILE)
            if rows_to_process < len(df):
                print(f"    Limiting to {rows_to_process} rows for performance")

            for i, row in df.head(rows_to_process).iterrows():
                if total_docs_added >= MAX_TOTAL_DOCUMENTS:
                    break

                # For budget/economic data CSVs, combine all columns
                content = ' '.join([f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])])

                # Skip very short content
                if len(content.strip()) < 50:
                    continue

                document = Document(
                    page_content=content,
                    metadata={
                        "source": csv_file,
                        "full_path": csv_path,
                        "row": i,
                        "type": "csv"
                    },
                    id=str(doc_counter)
                )
                documents.append(document)
                ids.append(str(doc_counter))
                doc_counter += 1
                total_docs_added += 1
        except Exception as e:
            print(f"  Error loading CSV {csv_file}: {e}")

    # Load Excel files (both .xlsx and .xls)
    excel_files = [f for f in all_files if f.endswith(('.xlsx', '.xls'))]
    print(f"Found {len(excel_files)} Excel files")

    for excel_file in excel_files:
        if total_docs_added >= MAX_TOTAL_DOCUMENTS:
            print(f"Reached maximum document limit ({MAX_TOTAL_DOCUMENTS})")
            break

        excel_path = os.path.join(search_directory, excel_file)
        print(f"  Loading Excel: {excel_file}")

        sheets_data = load_excel_file(excel_path, excel_file)

        file_doc_count = 0
        for sheet_name, df in sheets_data:
            if total_docs_added >= MAX_TOTAL_DOCUMENTS or file_doc_count >= MAX_DOCUMENTS_PER_FILE:
                break

            # Limit rows per sheet
            rows_to_process = min(len(df), MAX_DOCUMENTS_PER_FILE - file_doc_count)

            for i, row in df.head(rows_to_process).iterrows():
                if total_docs_added >= MAX_TOTAL_DOCUMENTS or file_doc_count >= MAX_DOCUMENTS_PER_FILE:
                    break

                # Skip rows that are mostly empty
                non_empty_values = [str(val) for val in row.values if pd.notna(val) and str(val).strip()]
                if len(non_empty_values) == 0:
                    continue

                content = ' '.join([f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])])

                # Skip very short content
                if len(content.strip()) < 50:
                    continue

                document = Document(
                    page_content=content,
                    metadata={
                        "source": excel_file,
                        "full_path": excel_path,
                        "sheet": sheet_name,
                        "row": i,
                        "type": "excel"
                    },
                    id=str(doc_counter)
                )
                documents.append(document)
                ids.append(str(doc_counter))
                doc_counter += 1
                total_docs_added += 1
                file_doc_count += 1

    # Load PDF documents
    pdf_files = [f for f in all_files if f.endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files")

    for pdf_file in pdf_files:
        if total_docs_added >= MAX_TOTAL_DOCUMENTS:
            print(f"Reached maximum document limit ({MAX_TOTAL_DOCUMENTS})")
            break

        pdf_path = os.path.join(search_directory, pdf_file)
        print(f"  Loading PDF: {pdf_file}")

        pdf_content = extract_pdf_content(pdf_path)

        if pdf_content:
            print(f"    Extracted {len(pdf_content)} characters")
            # Use larger chunks and limit number of chunks per PDF
            chunks = split_text_into_chunks(pdf_content, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

            # Limit chunks per PDF file
            max_chunks = min(len(chunks), MAX_DOCUMENTS_PER_FILE)
            if max_chunks < len(chunks):
                print(f"    Limiting to {max_chunks} chunks for performance")

            print(f"    Processing {max_chunks} chunks")

            for j, chunk in enumerate(chunks[:max_chunks]):
                if total_docs_added >= MAX_TOTAL_DOCUMENTS:
                    break

                # Skip very short chunks
                if len(chunk.strip()) < 100:
                    continue

                document = Document(
                    page_content=chunk,
                    metadata={
                        "source": pdf_file,
                        "full_path": pdf_path,
                        "chunk": j,
                        "type": "pdf"
                    },
                    id=str(doc_counter)
                )
                documents.append(document)
                ids.append(str(doc_counter))
                doc_counter += 1
                total_docs_added += 1
        else:
            print(f"    Could not extract content from PDF")

    # Load text documents
    text_files = [f for f in all_files if f.endswith('.txt')]
    print(f"Found {len(text_files)} text files")

    for text_file in text_files:
        text_path = os.path.join(search_directory, text_file)
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"  Loading text file: {text_file} ({len(content)} characters)")

                # Split large documents into chunks
                chunks = split_text_into_chunks(content, chunk_size=1000, overlap=200)
                print(f"    Split into {len(chunks)} chunks")

                for j, chunk in enumerate(chunks):
                    document = Document(
                        page_content=chunk,
                        metadata={
                            "source": text_file,
                            "full_path": text_path,
                            "chunk": j,
                            "type": "text"
                        },
                        id=str(doc_counter)
                    )
                    documents.append(document)
                    ids.append(str(doc_counter))
                    doc_counter += 1
        except UnicodeDecodeError:
            print(f"  Error: Could not decode {text_file} as UTF-8. Skipping...")
        except Exception as e:
            print(f"  Error loading text file {text_file}: {e}")

    # Load JSON files (bonus feature for economic data)
    json_files = [f for f in all_files if f.endswith('.json')]
    if json_files:
        print(f"Found {len(json_files)} JSON files")

        for json_file in json_files:
            json_path = os.path.join(search_directory, json_file)
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    print(f"  Loading JSON: {json_file}")

                    # Convert JSON to text representation
                    content = json.dumps(json_data, indent=2)

                    # If JSON is large, split into chunks
                    if len(content) > 1000:
                        chunks = split_text_into_chunks(content, chunk_size=1000, overlap=200)
                        for j, chunk in enumerate(chunks):
                            document = Document(
                                page_content=chunk,
                                metadata={
                                    "source": json_file,
                                    "full_path": json_path,
                                    "chunk": j,
                                    "type": "json"
                                },
                                id=str(doc_counter)
                            )
                            documents.append(document)
                            ids.append(str(doc_counter))
                            doc_counter += 1
                    else:
                        document = Document(
                            page_content=content,
                            metadata={
                                "source": json_file,
                                "full_path": json_path,
                                "type": "json"
                            },
                            id=str(doc_counter)
                        )
                        documents.append(document)
                        ids.append(str(doc_counter))
                        doc_counter += 1
            except Exception as e:
                print(f"  Error loading JSON {json_file}: {e}")

    print(f"\nTotal documents loaded: {len(documents)}")
    return documents, ids


def split_text_into_chunks(text, chunk_size=1000, overlap=200):
    """
    Split text into overlapping chunks
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
        if end >= len(text):
            break
    return chunks


def extract_pdf_content(pdf_path):
    """
    Extract text content from PDF files
    """
    try:
        content = ""
        with open(pdf_path, 'rb') as file:
            if 'PyPDF2' in str(type(PyPDF2)):
                # Using PyPDF2
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():  # Only add non-empty pages
                        content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            else:
                # Using pypdf
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():
                        content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"

        return content if content.strip() else None

    except Exception as e:
        print(f"    Error extracting PDF content: {e}")
        return None


def load_excel_file(excel_path, file_name):
    """
    Load Excel files with support for both .xlsx and .xls formats
    """
    sheets_data = []

    try:
        # Try loading as .xlsx first (works for both .xlsx and newer .xls files)
        try:
            xlsx_file = pd.ExcelFile(excel_path)
            for sheet_name in xlsx_file.sheet_names:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    if not df.empty:
                        sheets_data.append((sheet_name, df))
                        print(f"    Sheet: {sheet_name} ({len(df)} rows)")
                except Exception as e:
                    print(f"    Error reading sheet {sheet_name}: {e}")

        except Exception as e:
            # If it fails and it's a .xls file, try with xlrd if available
            if file_name.endswith('.xls'):
                print(f"    Trying to read .xls file with xlrd...")
                try:
                    xlsx_file = pd.ExcelFile(excel_path, engine='xlrd')
                    for sheet_name in xlsx_file.sheet_names:
                        try:
                            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine='xlrd')
                            if not df.empty:
                                sheets_data.append((sheet_name, df))
                                print(f"    Sheet: {sheet_name} ({len(df)} rows)")
                        except Exception as sheet_e:
                            print(f"    Error reading sheet {sheet_name}: {sheet_e}")
                except Exception as xlrd_e:
                    print(f"    Error with xlrd: {xlrd_e}")
            else:
                raise e

    except Exception as e:
        if file_name.endswith('.xls'):
            print(f"    Error: Cannot read .xls file without xlrd. Install with: pip install xlrd")
        else:
            print(f"    Error loading Excel file: {e}")

    return sheets_data


# Configuration - Set your documents folder here
DOCUMENTS_FOLDER = "/Users/mac/Downloads/data"  # Set to None for current directory, or specify path like "documents" or "/path/to/documents"

# Optimization settings
MAX_DOCUMENTS_PER_FILE = 50  # Limit documents per file to prevent overload
MAX_TOTAL_DOCUMENTS = 1000  # Maximum total documents to process
CHUNK_SIZE = 2000  # Larger chunks to reduce total number
CHUNK_OVERLAP = 400  # Overlap for context

# Set up vector store
db_location = "./chroma_langchain_db"
add_documents = not os.path.exists(db_location)

if add_documents:
    print("Setting up vector database...")
    print(f"Processing with limits: {MAX_DOCUMENTS_PER_FILE} docs per file, {MAX_TOTAL_DOCUMENTS} total max")
    documents, ids = load_documents(DOCUMENTS_FOLDER)

    if len(documents) > MAX_TOTAL_DOCUMENTS:
        print(f"Warning: Found {len(documents)} documents, limiting to {MAX_TOTAL_DOCUMENTS} for performance")
        documents = documents[:MAX_TOTAL_DOCUMENTS]
        ids = ids[:MAX_TOTAL_DOCUMENTS]

    print(f"Processing {len(documents)} document chunks")
else:
    documents, ids = [], []

vector_store = Chroma(
    collection_name="economic_documents",
    persist_directory=db_location,
    embedding_function=embeddings
)

if add_documents and documents:
    print("Adding documents to vector store...")

    # Add documents in batches to show progress and prevent memory issues
    batch_size = 50
    total_batches = (len(documents) + batch_size - 1) // batch_size

    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        current_batch = (i // batch_size) + 1

        print(f"  Processing batch {current_batch}/{total_batches} ({len(batch_docs)} documents)")

        try:
            vector_store.add_documents(documents=batch_docs, ids=batch_ids)
            print(f"  ✓ Batch {current_batch} completed")
        except Exception as e:
            print(f"  ✗ Error in batch {current_batch}: {e}")
            continue

    print("✓ All documents added successfully")

retriever = vector_store.as_retriever(
    search_kwargs={"k": 10}  # Increased to get more context
)

# Economic data extraction template
extraction_template = """
You are an expert economic analyst extracting specific data from government budget and economic documents.

Based on the following document content, extract the economic indicators listed below. 
Provide specific numerical values, percentages, and concrete data points.

Document Content:
{content}

Extract the following economic indicators (provide "N/A" if not found):

**1. Economic Growth (GDP)**
- GDP growth rate (%)
- Agriculture sector growth (%)
- Industry sector growth (%)
- Services sector growth (%)
- Previous year GDP growth for comparison

**2. Inflation Data**
- Year-end inflation rate (%)
- Average annual inflation rate (%)
- Food inflation rate (%)
- Non-food inflation rate (%)

**3. Government Finances**
- Total revenue (amount and currency)
- Tax revenue (amount)
- Non-tax revenue (amount)
- Total expenditure (amount)
- Fiscal deficit/surplus (amount and % of GDP)
- Budget vs actual variance

**4. Government Debt**
- Total external debt (amount)
- Total domestic debt (amount)
- Debt-to-GDP ratio (%)
- Debt service payments (amount)

**5. Exchange Rate**
- Official exchange rate (local currency per USD)
- Exchange rate depreciation/appreciation (%)
- Parallel market rate if mentioned

**6. Monetary Indicators**
- Bank rate/Policy rate (%)
- Treasury bill rates (%)
- Commercial bank lending rates (%)
- Money supply growth (%)

**7. External Trade**
- Total exports (value)
- Total imports (value)
- Trade balance (surplus/deficit)
- Current account balance
- Foreign reserves level

**8. Economic Targets/Projections**
- GDP growth target for next year (%)
- Inflation target (%)
- Fiscal deficit target (% of GDP)
- Other macroeconomic targets

**9. Sector Allocations**
- Education budget allocation (amount and %)
- Health budget allocation (amount and %)
- Infrastructure budget allocation (amount and %)
- Agriculture budget allocation (amount and %)

Extract only factual data with specific numbers. Include the year/period for each indicator.
Format as clear bullet points with values and units.
"""

extraction_prompt = ChatPromptTemplate.from_template(extraction_template)
extraction_chain = extraction_prompt | model


def extract_economic_data():
    """
    Main function to extract economic data from all loaded documents
    """
    print("Extracting economic data from documents...")

    # Define key economic search terms
    economic_queries = [
        "GDP growth rate economic growth",
        "inflation rate consumer prices",
        "government revenue tax collection expenditure",
        "fiscal deficit surplus budget balance",
        "external debt domestic debt government borrowing",
        "exchange rate currency depreciation cedi dollar",
        "interest rates monetary policy bank rate",
        "exports imports trade balance payments",
        "economic projections targets forecast",
        "budget allocation education health infrastructure spending"
    ]

    all_extracted_data = []

    for query in economic_queries:
        print(f"Searching for: {query}")

        # Retrieve relevant documents
        relevant_docs = retriever.invoke(query)

        if relevant_docs:
            # Combine content from relevant documents
            combined_content = "\n\n".join([doc.page_content for doc in relevant_docs[:5]])  # Use top 5 results

            # Extract data using the model
            extracted = extraction_chain.invoke({"content": combined_content})
            all_extracted_data.append({
                "query": query,
                "extracted_data": extracted,
                "source_docs": len(relevant_docs)
            })

    # Combine all extracted data
    final_extraction = combine_extracted_data(all_extracted_data)

    return final_extraction


def combine_extracted_data(all_extracted_data):
    """
    Combine and deduplicate extracted data from multiple queries
    """
    print("Combining and processing extracted data...")

    combined_data = {
        "extraction_summary": f"Data extracted from {len(all_extracted_data)} economic queries",
        "economic_indicators": {},
        "raw_extractions": all_extracted_data
    }

    # Categories for organizing data
    categories = {
        "Economic Growth": [],
        "Inflation": [],
        "Government Finances": [],
        "Government Debt": [],
        "Exchange Rate": [],
        "Monetary Policy": [],
        "External Trade": [],
        "Economic Projections": [],
        "Budget Allocations": []
    }

    # Process each extraction
    for extraction in all_extracted_data:
        data = extraction["extracted_data"]

        # Simple parsing to categorize data (you may need to enhance this)
        if "GDP" in extraction["query"] or "growth" in extraction["query"]:
            categories["Economic Growth"].append(data)
        elif "inflation" in extraction["query"]:
            categories["Inflation"].append(data)
        elif "revenue" in extraction["query"] or "expenditure" in extraction["query"]:
            categories["Government Finances"].append(data)
        elif "debt" in extraction["query"]:
            categories["Government Debt"].append(data)
        elif "exchange" in extraction["query"]:
            categories["Exchange Rate"].append(data)
        elif "interest" in extraction["query"] or "monetary" in extraction["query"]:
            categories["Monetary Policy"].append(data)
        elif "export" in extraction["query"] or "import" in extraction["query"]:
            categories["External Trade"].append(data)
        elif "projection" in extraction["query"] or "target" in extraction["query"]:
            categories["Economic Projections"].append(data)
        elif "allocation" in extraction["query"] or "spending" in extraction["query"]:
            categories["Budget Allocations"].append(data)

    combined_data["economic_indicators"] = categories

    return combined_data


# Function to clear and rebuild the database if needed
def clear_vector_database():
    """
    Clear the existing vector database to start fresh
    """
    import shutil
    if os.path.exists(db_location):
        shutil.rmtree(db_location)
        print("✓ Vector database cleared")
    else:
        print("No existing database to clear")


# Function to get retriever (for backward compatibility)
def get_retriever():
    return retriever