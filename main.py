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
You are an expert economic data processor analyzing government budget and economic documents from 2000 to present.

Your task is to extract ALL economic indicators and financial data from the provided text and output them in a structured CSV-ready format.

**CRITICAL PROCESSING INSTRUCTIONS:**
1. Extract EVERY numerical economic indicator you find
2. Identify what each number represents based on context
3. Output in EXACT CSV format with proper headers
4. EXTRACT THE ACTUAL YEAR/PERIOD from the document - DO NOT assume any year
5. CURRENCY HANDLING: Identify and convert currencies
   - Old Cedis (pre-2007): Convert to New Cedis by dividing by 10,000
   - New Cedis/Ghana Cedis (GHS): Use as is
   - Note original currency and any conversions made
6. DATA TYPE CLASSIFICATION: Distinguish between:
   - Actual/Outturn: Historical realized data
   - Provisional: Preliminary estimates
   - Revised: Updated historical data
   - Projected/Budget: Forward-looking estimates
   - Target: Policy goals
7. PERIOD STANDARDIZATION: Identify and note:
   - Fiscal Year (e.g., FY2015 = Oct 2014 - Sep 2015)
   - Calendar Year (Jan-Dec)
   - Quarterly/Monthly periods
8. METHODOLOGY CHANGES: Flag when calculation methods change
9. COMPARATIVE DATA: Extract both current and reference year data when present
10. REGIONAL DATA: Extract provincial/regional breakdowns when available
11. INDICATOR STANDARDIZATION: Use consistent names for same indicators across years
12. VALIDATION FLAGS: Mark suspicious or unusual values

**Input Data:**
{extracted_data}

**FIELD EXTRACTION INSTRUCTIONS:**

- **EXTRACT_VALUE**: Final processed/converted value for analysis
- **EXTRACT_ORIGINAL**: Original value as stated in document (before any conversions)
- **EXTRACT_ORIG_CURR**: Original currency mentioned (Old Cedis, New Cedis, GHS, USD, etc.)
- **EXTRACT_CONV_CURR**: Converted currency (standardize to GHS or USD where applicable)
- **EXTRACT_YEAR**: Actual year from document (2000-2025)
- **EXTRACT_PERIOD_TYPE**: Calendar Year, Fiscal Year, Q1/Q2/Q3/Q4, Monthly, End-of-period
- **EXTRACT_DATA_TYPE**: Actual, Provisional, Revised, Projected, Budget, Target
- **EXTRACT_SOURCE**: Page number, section, table reference
- **EXTRACT_METHOD_NOTES**: Note any methodology changes, calculation differences, or data collection changes
- **EXTRACT_FLAG**: Normal, Suspicious (unusual values), Missing_Context, Methodology_Change
- **EXTRACT_COMPARATIVE**: Previous year comparison data if mentioned (e.g., "compared to 4.2% in 2015")
- **EXTRACT_REGIONAL**: Regional/provincial breakdown if available (e.g., "Ashanti: 5.2%, Northern: 3.1%")
- **EXTRACT_CONTEXT**: Brief context about the data point

**CURRENCY CONVERSION RULES:**
- Old Cedis (₵, pre-2007): Divide by 10,000 to convert to New Cedis/GHS
- New Cedis (GH₵, 2007-2014): Use as is, note as GHS equivalent
- Ghana Cedis (GHS, 2014+): Use as is
- Always preserve original values and note conversions

**DATA TYPE IDENTIFICATION:**
- Look for keywords: "actual", "outturn", "realized" = Actual
- Look for keywords: "provisional", "preliminary", "estimated" = Provisional
- Look for keywords: "revised", "updated", "corrected" = Revised
- Look for keywords: "projected", "forecast", "expected" = Projected
- Look for keywords: "budget", "allocated" = Budget
- Look for keywords: "target", "goal", "aimed" = Target

**PERIOD TYPE IDENTIFICATION:**
- Look for: "FY2015", "fiscal year" = Fiscal Year
- Look for: "2015", "calendar year" = Calendar Year
- Look for: "Q1", "first quarter" = Quarterly
- Look for: "January", "month" = Monthly
- Look for: "end-December", "as at" = End-of-period

**METHODOLOGY CHANGE DETECTION:**
- Note when documents mention "rebased", "new methodology", "revised calculation"
- Flag when same indicator has different definitions across years
- Note changes in base years, coverage, or classification

**VALIDATION FLAGS:**
- Normal: Data appears consistent with expectations
- Suspicious: Unusual values (e.g., 200% inflation, negative GDP)
- Missing_Context: Number found but insufficient context
- Methodology_Change: Calculation method changed

**REGIONAL DATA EXTRACTION:**
- Extract any provincial, regional, or district-level breakdowns
- Format as: "Region1: Value1, Region2: Value2"
- Include urban/rural splits if available

**COMPARATIVE DATA EXTRACTION:**
- Extract year-over-year comparisons mentioned in text
- Format as: "Previous: Value (Year), Change: X% increase/decrease"
- Include multi-year trends if mentioned

**REQUIRED OUTPUT FORMAT - CSV DATA:**

Indicator,Value,Original_Value,Unit,Original_Currency,Converted_Currency,Category,Year,Period_Type,Data_Type,Source_Info,Methodology_Notes,Validation_Flag,Comparative_Data,Regional_Breakdown,Document_Context
GDP Growth Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Real GDP Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Nominal GDP Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Agriculture Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Industry Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Services Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Manufacturing Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Mining Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Growth,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Inflation Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Price Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Consumer Price Index,EXTRACT_VALUE,EXTRACT_ORIGINAL,Index,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Price Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Food Inflation,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Price Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Non-food Inflation,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Price Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Core Inflation,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Price Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Total Government Revenue,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Tax Revenue,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Non-tax Revenue,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Total Government Expenditure,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Current Expenditure,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Capital Expenditure,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Fiscal Balance,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Fiscal Deficit,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Fiscal Deficit to GDP Ratio,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Government Finances,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
External Debt Stock,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Debt Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Domestic Debt Stock,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Debt Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Total Public Debt,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Debt Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Debt to GDP Ratio,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Debt Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Debt Service Payments,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Debt Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Exchange Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,Local per USD,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Policy Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Bank Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Treasury Bill Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Prime Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Money Supply Growth,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Monetary Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Total Exports,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Total Imports,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Trade Balance,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Current Account Balance,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Capital Account Balance,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Foreign Reserves,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,External Trade,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Education Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Health Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Infrastructure Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Agriculture Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Defense Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Roads Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Energy Budget,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Sectoral Spending,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
GDP Nominal,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Size,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
GDP Real,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Size,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
GDP Per Capita,EXTRACT_VALUE,EXTRACT_ORIGINAL,EXTRACT_UNIT,EXTRACT_ORIG_CURR,EXTRACT_CONV_CURR,Economic Size,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Population,EXTRACT_VALUE,EXTRACT_ORIGINAL,Millions,N/A,N/A,Demographics,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Unemployment Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,N/A,N/A,Labor Market,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT
Poverty Rate,EXTRACT_VALUE,EXTRACT_ORIGINAL,%,N/A,N/A,Social Indicators,EXTRACT_YEAR,EXTRACT_PERIOD_TYPE,EXTRACT_DATA_TYPE,EXTRACT_SOURCE,EXTRACT_METHOD_NOTES,EXTRACT_FLAG,EXTRACT_COMPARATIVE,EXTRACT_REGIONAL,EXTRACT_CONTEXT

**CRITICAL INSTRUCTIONS:**
- Replace ALL placeholder text with actual extracted information
- If any field cannot be determined, use "N/A"
- Add additional rows for any indicators not listed but found in documents
- Maintain data integrity - never make up values
- Extract ALL economic data found, not just the template indicators
- Handle multi-year data (some documents cover several years)
- Note any off-budget items, contingent liabilities, or special funds

**CRITICAL INSTRUCTIONS:**
- Replace ALL "EXTRACT_VALUE" with actual numbers found in the document
- Replace ALL "EXTRACT_YEAR" with the actual year from the document (2000-2025)
- Replace ALL "EXTRACT_CURRENCY" with actual currency (Cedis, New Cedis, GHS, USD, etc.)
- Replace ALL "EXTRACT_UNIT" with actual units (Millions, Billions, Thousands, etc.)
- Replace ALL "EXTRACT_SOURCE" with page number or section reference
- Replace ALL "EXTRACT_CONTEXT" with brief context about the data
- Replace ALL "EXTRACT_PERIOD" with actual period (Annual, Quarterly, Monthly, End-of-period)
- If any indicator is not found, use "N/A" for that entire row
- Add MORE rows for any additional economic indicators you discover
- Handle currency changes (Cedis → New Cedis → Ghana Cedis)
- Extract ALL years present in the document (some documents cover multiple years)
- Include both historical data and projections where available

**EXTRACT ALL ECONOMIC DATA YOU FIND IN THIS EXACT FORMAT.**
**ADAPT TO THE ACTUAL CONTENT - DO NOT USE PLACEHOLDER VALUES.**
**PROVIDE COMPLETE CSV DATA READY FOR ANALYSIS.**
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