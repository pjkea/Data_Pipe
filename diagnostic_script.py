import os
from vector import vector_store, retriever
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


def diagnose_vector_database():
    """
    Diagnostic script to check what's in the vector database
    """
    print("VECTOR DATABASE DIAGNOSTIC")
    print("=" * 50)

    # Check if database exists
    db_location = "./chroma_langchain_db"
    if not os.path.exists(db_location):
        print("❌ Vector database does not exist!")
        return False

    print("✅ Vector database folder exists")

    # Check database contents
    try:
        # Initialize embeddings
        embeddings = OllamaEmbeddings(model="mxbai-embed-large")

        # Connect to existing database
        vector_store = Chroma(
            collection_name="economic_documents",
            persist_directory=db_location,
            embedding_function=embeddings
        )

        # Get collection info
        collection = vector_store._collection
        count = collection.count()

        print(f"📊 Total documents in database: {count}")

        if count == 0:
            print("❌ Database is empty! No documents were loaded.")
            return False

        # Test basic retrieval
        print("\n🔍 Testing retrieval with sample queries...")

        test_queries = [
            "GDP growth",
            "inflation",
            "government revenue",
            "budget",
            "economic",
            "Ghana",
            "2000",
            "fiscal",
            "debt"
        ]

        for query in test_queries:
            try:
                results = retriever.invoke(query)
                print(f"  '{query}': Found {len(results)} results")

                if results:
                    # Show sample content
                    sample_content = results[0].page_content[:200] + "..."
                    print(f"    Sample: {sample_content}")
                    print(f"    Source: {results[0].metadata.get('source', 'Unknown')}")
                    break  # Just show one example

            except Exception as e:
                print(f"  '{query}': Error - {e}")

        return True

    except Exception as e:
        print(f"❌ Error accessing database: {e}")
        return False


def check_document_files():
    """
    Check what document files are available
    """
    print("\n📁 DOCUMENT FILES CHECK")
    print("=" * 30)

    current_dir = "."
    files_found = {
        "PDF": [],
        "Excel": [],
        "CSV": [],
        "Text": []
    }

    for file in os.listdir(current_dir):
        if file.endswith('.pdf'):
            files_found["PDF"].append(file)
        elif file.endswith(('.xlsx', '.xls')):
            files_found["Excel"].append(file)
        elif file.endswith('.csv'):
            files_found["CSV"].append(file)
        elif file.endswith('.txt'):
            files_found["Text"].append(file)

    for file_type, file_list in files_found.items():
        print(f"{file_type} files ({len(file_list)}):")
        for file in file_list[:5]:  # Show first 5
            print(f"  - {file}")
        if len(file_list) > 5:
            print(f"  ... and {len(file_list) - 5} more")

    return files_found


def test_manual_extraction():
    """
    Test manual extraction from a sample document
    """
    print("\n🧪 MANUAL EXTRACTION TEST")
    print("=" * 30)

    # Try to get some content directly
    try:
        results = retriever.invoke("Ghana budget revenue expenditure GDP inflation")

        if results:
            print(f"✅ Found {len(results)} relevant documents")
            print("\nSample content:")
            print("-" * 40)
            print(results[0].page_content[:500])
            print("-" * 40)
            print(f"Source: {results[0].metadata}")
        else:
            print("❌ No results found for manual test")

    except Exception as e:
        print(f"❌ Error in manual test: {e}")


if __name__ == "__main__":
    print("Running comprehensive diagnostic...\n")

    # Check files
    files = check_document_files()

    # Check database
    db_ok = diagnose_vector_database()

    # Test extraction
    if db_ok:
        test_manual_extraction()

    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")

    if not db_ok:
        print("\n🔧 RECOMMENDED ACTIONS:")
        print("1. Delete the chroma_langchain_db folder")
        print("2. Run the vector.py setup again")
        print("3. Check that PDF/Excel libraries are installed:")
        print("   pip install PyPDF2 xlrd openpyxl")