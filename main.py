from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever, extract_economic_data
import json
import pandas as pd
from datetime import datetime
import os

model = OllamaLLM(model="llama3.2")

# Template for processing extracted data into structured format
processing_template = """
You are an expert economic data processor. You have been provided with extracted economic data from government budget documents.

Your task is to structure this data into a clean, processable format with the following categories:

**Economic Data Categories:**
1. Economic Growth (GDP)
2. Inflation and Cost of Living  
3. Government Revenue and Expenditure
4. Government Debt
5. Exchange Rate and Currency
6. Monetary Policy
7. Balance of Payments & Trade
8. Economic Projections
9. Policy Priorities

**Instructions:**
- Extract specific numerical values where available
- Maintain data integrity and accuracy
- Use "N/A" for unavailable data
- Include units (%, billions, millions, etc.)
- Preserve year references and time periods
- Note data sources/page references when available

**Input Data:**
{extracted_data}

**Required Output Format:**
Provide a structured JSON-like format that can be easily converted to tables or datasets.
Focus on extracting concrete numbers, percentages, and measurable indicators.
"""

prompt = ChatPromptTemplate.from_template(processing_template)
chain = prompt | model


def process_economic_data():
    """
    Main function to extract and process economic data from documents
    """
    print("Starting economic data extraction...")
    print("=" * 60)

    try:
        # Step 1: Extract raw economic data using vector.py
        print("1. Extracting economic data from documents...")
        raw_data = extract_economic_data()

        if not raw_data:
            print("No data extracted. Please check your documents and vector setup.")
            return None

        # Step 2: Process and structure the extracted data
        print("2. Processing and structuring the data...")
        structured_data = chain.invoke({"extracted_data": raw_data})

        # Step 3: Create processable output
        print("3. Creating processable output formats...")
        output_data = create_output_formats(structured_data, raw_data)

        print("✓ Economic data extraction completed successfully!")
        return output_data

    except Exception as e:
        print(f"Error during data extraction: {str(e)}")
        return None


def create_output_formats(structured_data, raw_data):
    """
    Create multiple output formats for the extracted data
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_data = {
        "extraction_timestamp": datetime.now().isoformat(),
        "structured_data": structured_data,
        "raw_data": raw_data
    }

    # Create output directory if it doesn't exist
    output_dir = "economic_extractions"
    os.makedirs(output_dir, exist_ok=True)

    # 1. Save as JSON for programmatic processing
    json_file = os.path.join(output_dir, f"economic_data_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"✓ JSON file saved: {json_file}")

    # 2. Save as structured text for human reading
    txt_file = os.path.join(output_dir, f"economic_data_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("ECONOMIC DATA EXTRACTION REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("STRUCTURED DATA:\n")
        f.write("-" * 30 + "\n")
        f.write(str(structured_data))
        f.write("\n\n" + "=" * 50 + "\n")
        f.write("RAW EXTRACTED DATA:\n")
        f.write("-" * 30 + "\n")
        f.write(str(raw_data))
    print(f"✓ Text file saved: {txt_file}")

    # 3. Try to create CSV if data is tabular
    try:
        csv_file = os.path.join(output_dir, f"economic_indicators_{timestamp}.csv")
        create_csv_output(structured_data, csv_file)
        print(f"✓ CSV file saved: {csv_file}")
    except Exception as e:
        print(f"Note: Could not create CSV format: {str(e)}")

    return {
        "files_created": {
            "json": json_file,
            "text": txt_file,
            "csv": csv_file if 'csv_file' in locals() else None
        },
        "data": output_data
    }


def create_csv_output(structured_data, csv_file):
    """
    Create CSV from LLM-structured economic data
    """
    try:
        # The LLM should return properly formatted CSV data
        csv_content = str(structured_data)

        # Find the CSV section in the response
        lines = csv_content.split('\n')
        csv_lines = []
        in_csv_section = False

        for line in lines:
            line = line.strip()

            # Look for CSV header or data rows
            if 'Indicator,Value,Unit' in line or in_csv_section:
                in_csv_section = True
                if ',' in line and line.count(',') >= 6:  # Valid CSV row
                    csv_lines.append(line)
                elif line == '' or 'EXTRACT ALL' in line:  # End of CSV
                    break

        # Write to file
        if csv_lines:
            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(csv_lines))
            print(f"✓ CSV created with {len(csv_lines) - 1} data rows")  # -1 for header
        else:
            # Fallback: create basic template
            print("No structured CSV data found, creating template...")
            template_data = """Indicator,Value,Unit,Category,Year,Source_Page,Data_Type,Notes
                                GDP Growth Rate,N/A,%,Economic Growth,N/A,N/A,N/A,Not found in documents
                                Inflation Rate,N/A,%,Price Indicators,N/A,N/A,N/A,Not found in documents
                                Government Revenue,N/A,Currency,Government Finances,N/A,N/A,N/A,Not found in documents"""

            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write(template_data)

    except Exception as e:
        print(f"Error creating CSV: {e}")
        # Create minimal fallback
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("Indicator,Value,Unit,Category,Year,Source_Page,Data_Type,Notes\n")
            f.write("Error,Data extraction failed,N/A,Error,N/A,N/A,N/A,Check extraction process\n")


def display_summary(output_data):
    """
    Display a summary of extracted data
    """
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    if output_data and "data" in output_data:
        print("✓ Data extraction completed")
        print(f"✓ Files created in: economic_extractions/")

        files = output_data.get("files_created", {})
        for file_type, file_path in files.items():
            if file_path:
                print(f"  - {file_type.upper()}: {os.path.basename(file_path)}")

        print(f"\nExtracted data preview:")
        print("-" * 30)
        # Show first few lines of structured data
        structured = str(output_data["data"]["structured_data"])
        preview = structured[:500] + "..." if len(structured) > 500 else structured
        print(preview)

    else:
        print("✗ No data extracted")

    print("=" * 60)


def main():
    """
    Main execution function
    """
    print("ECONOMIC DATA EXTRACTION SYSTEM")
    print("=" * 60)
    print("Extracting economic indicators from loaded documents...")
    print()

    # Process the economic data
    result = process_economic_data()

    # Display summary
    display_summary(result)

    return result


if __name__ == "__main__":
    main()