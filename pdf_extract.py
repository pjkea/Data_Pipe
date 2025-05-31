import os
import re
import pandas as pd
import pdfplumber
import tabula
from pathlib import Path
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GhanaFinancialDataExtractor:
    """Extract financial data from Ghana government PDFs and budget reports"""

    def __init__(self, output_dir="extracted_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Common patterns in Ghana financial documents
        self.patterns = {
            'currency': r'GH[¢₵]\s*[\d,]+\.?\d*|GHS\s*[\d,]+\.?\d*|₵\s*[\d,]+\.?\d*',
            'percentage': r'\d+\.?\d*\s*%',
            'year': r'20\d{2}|19\d{2}',
            'fiscal_year': r'FY\s*20\d{2}|20\d{2}/\d{2}|20\d{2}-\d{2}',
            'amount': r'[\d,]+\.?\d*\s*(?:million|billion|thousand)?',
        }

        # Keywords to look for in Ghana budget documents
        self.keywords = {
            'revenue': ['revenue', 'income', 'receipts', 'tax', 'non-tax'],
            'expenditure': ['expenditure', 'spending', 'payments', 'expenses'],
            'gdp': ['gdp', 'gross domestic product'],
            'debt': ['debt', 'borrowing', 'loans'],
            'deficit': ['deficit', 'surplus', 'balance'],
            'inflation': ['inflation', 'cpi', 'consumer price'],
        }

    def extract_tables_from_pdf(self, pdf_path):
        """Extract tables from PDF using multiple methods"""
        tables_data = []

        # Method 1: Using pdfplumber
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for j, table in enumerate(tables):
                        if table:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            df['page'] = i + 1
                            df['table_id'] = f"page_{i + 1}_table_{j + 1}"
                            tables_data.append(df)
                            logger.info(f"Extracted table from page {i + 1} using pdfplumber")
        except Exception as e:
            logger.error(f"Error with pdfplumber: {e}")

        # Method 2: Using tabula-py as backup
        try:
            dfs = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
            for i, df in enumerate(dfs):
                df['table_id'] = f"tabula_table_{i + 1}"
                tables_data.append(df)
                logger.info(f"Extracted table {i + 1} using tabula")
        except Exception as e:
            logger.error(f"Error with tabula: {e}")

        return tables_data

    def extract_text_from_pdf(self, pdf_path):
        """Extract raw text from PDF"""
        text_content = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        text_content.append({
                            'page': i + 1,
                            'text': text
                        })
        except Exception as e:
            logger.error(f"Error extracting text: {e}")

        return text_content

    def parse_financial_values(self, text):
        """Extract financial values from text using patterns"""
        results = {}

        # Extract currency amounts
        currency_matches = re.findall(self.patterns['currency'], text, re.IGNORECASE)
        if currency_matches:
            results['currency_values'] = [self.clean_amount(m) for m in currency_matches]

        # Extract percentages
        percentage_matches = re.findall(self.patterns['percentage'], text)
        if percentage_matches:
            results['percentages'] = percentage_matches

        # Extract years
        year_matches = re.findall(self.patterns['fiscal_year'], text)
        if not year_matches:
            year_matches = re.findall(self.patterns['year'], text)
        if year_matches:
            results['years'] = list(set(year_matches))

        return results

    def clean_amount(self, amount_str):
        """Clean and standardize amount strings"""
        # Remove currency symbols and spaces
        cleaned = re.sub(r'[GH¢₵\s]', '', amount_str)
        # Remove commas
        cleaned = cleaned.replace(',', '')

        try:
            return float(cleaned)
        except:
            return amount_str

    def identify_data_context(self, text, values):
        """Try to identify what the extracted values represent"""
        context = {}
        text_lower = text.lower()

        for category, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Find values near this keyword (within 50 characters)
                    pattern = f"{keyword}.{{0,50}}({'|'.join(map(re.escape, [str(v) for v in values[:5]]))})"
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    if matches:
                        if category not in context:
                            context[category] = []
                        context[category].extend(matches)

        return context

    def process_pdf(self, pdf_path):
        """Process a single PDF file"""
        pdf_path = Path(pdf_path)
        logger.info(f"Processing {pdf_path.name}")

        results = {
            'filename': pdf_path.name,
            'processed_date': datetime.now().isoformat(),
            'tables': [],
            'extracted_values': [],
            'text_data': []
        }

        # Extract tables
        tables = self.extract_tables_from_pdf(pdf_path)
        for table in tables:
            # Clean table data
            table = table.fillna('')
            # Look for financial values in the table
            for col in table.columns:
                if table[col].dtype == 'object':
                    table[col] = table[col].apply(
                        lambda x: self.clean_amount(x) if isinstance(x, str) and re.search(r'\d', x) else x)

            results['tables'].append({
                'id': table['table_id'].iloc[0] if 'table_id' in table.columns else 'unknown',
                'data': table.to_dict('records')
            })

        # Extract and parse text
        text_data = self.extract_text_from_pdf(pdf_path)
        for page_data in text_data:
            parsed_values = self.parse_financial_values(page_data['text'])
            if parsed_values:
                context = self.identify_data_context(page_data['text'],
                                                     parsed_values.get('currency_values', []))
                results['extracted_values'].append({
                    'page': page_data['page'],
                    'values': parsed_values,
                    'context': context
                })

        return results

    def process_directory(self, input_dir):
        """Process all PDFs in a directory"""
        input_path = Path(input_dir)
        pdf_files = list(input_path.glob('*.pdf'))

        logger.info(f"Found {len(pdf_files)} PDF files")

        all_results = []
        for pdf_file in pdf_files:
            try:
                result = self.process_pdf(pdf_file)
                all_results.append(result)

                # Save individual results
                output_file = self.output_dir / f"{pdf_file.stem}_extracted.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)

                logger.info(f"Saved results to {output_file}")
            except Exception as e:
                logger.error(f"Error processing {pdf_file}: {e}")

        # Compile all data into a summary
        self.create_summary_excel(all_results)

        return all_results

    def create_summary_excel(self, all_results):
        """Create a summary Excel file with all extracted data"""
        summary_file = self.output_dir / "ghana_financial_data_summary.xlsx"

        with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for result in all_results:
                summary_data.append({
                    'Filename': result['filename'],
                    'Tables Found': len(result['tables']),
                    'Values Extracted': len(result['extracted_values']),
                    'Processing Date': result['processed_date']
                })

            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            # All extracted values sheet
            all_values = []
            for result in all_results:
                for extraction in result['extracted_values']:
                    if 'currency_values' in extraction['values']:
                        for value in extraction['values']['currency_values']:
                            row = {
                                'Source': result['filename'],
                                'Page': extraction['page'],
                                'Value': value,
                                'Type': 'Currency'
                            }
                            # Add context if available
                            for category, contexts in extraction.get('context', {}).items():
                                if contexts:
                                    row['Category'] = category
                                    break
                            all_values.append(row)

            if all_values:
                pd.DataFrame(all_values).to_excel(writer, sheet_name='Extracted Values', index=False)

            logger.info(f"Created summary Excel file: {summary_file}")


# Example usage
if __name__ == "__main__":
    # Initialize the extractor
    extractor = GhanaFinancialDataExtractor(output_dir="ghana_data_output")

    # Example: Process a single PDF
    results = extractor.process_pdf("/Users/mac/Downloads/budgets/bud2000.pdf")

    # Example: Process all PDFs in a directory
    # all_results = extractor.process_directory("path/to/pdf_directory")

    # Demo with sample text extraction
    sample_text = """
    Ghana Budget Statement 2023
    Total Revenue: GH₵ 100,543.2 million
    Total Expenditure: GH₵ 135,745.8 million
    GDP Growth Rate: 3.5%
    Fiscal Deficit: GH₵ 35,202.6 million (7.5% of GDP)
    """

    # parsed = extractor.parse_financial_values(sample_text)
    # print("Demo - Parsed values from sample text:")
    # print(json.dumps(parsed, indent=2))