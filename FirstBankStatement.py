import pandas as pd
from BaseBankStatementReport import BankStatementReport
import re


class FirstBankStatement(BankStatementReport):

    def __init__(self, pdf_directory, password):
        super().__init__(pdf_directory, password)

    def get_opening_balance(self, text):
        pattern = r'Opening Balance[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            opening_balance = match.group(1)
            return opening_balance
        else:
            return None
        pass

    def get_closing_balance(self, text):
        pattern = r'Closing Balance[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            closing_balance = match.group(1)
            return closing_balance
        else:
            return None

    def get_transactions_table_header_mapping(self):
        return {
            'transdate': 'TransDate',
            'reference': 'Reference',
            'transaction_details': 'Transaction Details',
            'valuedate': 'ValueDate',
            'withdrawal': 'Withdrawal',
            'deposit': 'Deposit',
            'balance': 'Balance'
        }

    def get_transactions_table_headers(self, reader):
        table = reader.pages[0].extract_tables()[0]
        access_table_headers = table[0]

        header_mapping = self.get_transactions_table_header_mapping()
        header_columns = [header_mapping[col.replace('\n', ' ').lower().replace(' ', '_').replace('.', '').strip()]
                          for col in access_table_headers if col is not None]
        return header_columns

    def pad_header_with_unknown(self, rows, headers):
        if len(rows[0]) > len(headers):
            # New item to be inserted
            unknown = 'Unknown'

            # Index of "Value Date" in the list
            value_date_index = headers.index('Value Date')

            # Insert the new item before "Value Date"
            headers.insert(value_date_index, unknown)
            return headers
        else:
            return headers

    def get_transactions_table_rows(self, reader, page=0):
        split_balance_bf_balance = 0
        if page == 0:
            table = reader.pages[page].extract_tables()[0]
            rows_without_header = table[1:]
            balance_bf = [item for item in rows_without_header if 'Balance B/F' in item[0]]

            split_balance_bf = balance_bf[0][0].split()
            split_balance_bf_balance = split_balance_bf[len(split_balance_bf) - 1]
            balance_bf[0][2] = 'Balance B/F'
            balance_bf[0][6] = split_balance_bf_balance
        else:
            table = reader.pages[page].extract_tables()[0]
            rows_without_header = table[1:]
        rows_without_header = [item for item in rows_without_header if 'END OF STATEMENT' not in item[0]]
        rows_without_header = [item for item in rows_without_header if 'Balance B/F' not in item[0]]
        for row in rows_without_header:
            split_list = row[0].split()
            last_item_in_split_list = split_list[len(split_list) - 1]
            trans_date = split_list[0]
            reference = ''
            transaction_details = split_list[1] + ' ' + split_list[2] + ' ' + split_list[3] + last_item_in_split_list
            value_date = split_list[4]

            deposit = split_list[5]
            withdrawal = split_list[5]
            balance = split_list[len(split_list) - 2]
            row[0] = trans_date
            row[1] = reference
            row[2] = transaction_details
            row[3] = value_date
            row[4] = deposit
            row[5] = withdrawal
            row[6] = balance
        modified_rows = [[item.replace('\n', '').strip() if item else '' for item in row] for row in
                         rows_without_header]

        for index, row in enumerate(modified_rows):
            current_row = modified_rows[index]
            previous_row = modified_rows[index - 1]
            current_row_balance = current_row[6]
            previous_row_balance = previous_row[6]
            if index != 0:
                if current_row_balance > previous_row_balance:
                    balance = row[4]
                    row[4] = balance
                    row[5] = None
                else:
                    row[4] = None
                    row[5] = balance
            else:
                if current_row_balance > split_balance_bf_balance:
                    balance = row[4]
                    row[4] = balance
                    row[5] = None

        return balance_bf + modified_rows


first_bank_statement_pdf_path = "/Users/harmlessprince/python/pdfconverter/pdfs/firstbank.pdf"

bank_statement = FirstBankStatement(pdf_directory=first_bank_statement_pdf_path, password='81054')

reader, status, message = bank_statement.get_pdf_reader()
print(reader.pages[0].extract_text())
print(message)
if status == 0:
    exit()

text = bank_statement.get_pdf_page_text(reader)
cleaned_text = bank_statement.clean_text(text)

statement_period_extracted = bank_statement.get_statement_period(cleaned_text)
account_name_extracted = bank_statement.get_account_name(cleaned_text)
account_number_extracted = bank_statement.get_account_number(cleaned_text)
total_withdrawals_extracted = bank_statement.get_total_withdrawal(cleaned_text)
total_deposit_extracted = bank_statement.get_total_deposit(cleaned_text)
opening_balance_extracted = bank_statement.get_opening_balance(cleaned_text)
closing_balance_extracted = bank_statement.get_closing_balance(cleaned_text)
#
print("Extracted Bank Statement Period:", statement_period_extracted)
print("Extracted Account Name:", account_name_extracted)
print("Extracted Account Number: ", account_number_extracted)
print("Extracted Total Withdrawals:", total_withdrawals_extracted)
print("Extracted Total Deposit:", total_deposit_extracted)
print("Extracted Opening Balance:", opening_balance_extracted)
print("Extracted Closing Balance:", closing_balance_extracted)

headers = bank_statement.get_transactions_table_headers(reader)
rows = bank_statement.get_transactions_table_rows(reader, 0)

# Step 3: Create a DataFrame using pandas
df = pd.DataFrame(rows, columns=headers)

# # rename columns for uniformity
bank_statement.rename_column(df, 'TransDate', 'Transaction Date')
bank_statement.rename_column(df, 'ValueDate', 'Value Date')

df['Transaction Date'] = bank_statement.clean_date('Transaction Date', df, '%d-%b-%y')
df['Value Date'] = bank_statement.clean_date('Value Date', df, '%d-%b-%y')
df['Withdrawal'] = bank_statement.clean_money('Withdrawal', df)
df['Balance'] = bank_statement.clean_money('Balance', df)
df['Deposit'] = bank_statement.clean_money('Deposit', df)
df['Reference'] = df['Reference'].astype(str)
df['Transaction Details'] = bank_statement.clean_column(df, 'Transaction Details')

# Replace NaT values with a custom string, e.g., 'Not Available'
replacement_value = 'Invalid Date'
df['Value Date'] = df['Value Date'].fillna(replacement_value)
df['Transaction Date'] = df['Transaction Date'].fillna(replacement_value)
df['Withdrawal'] = df['Withdrawal'].fillna(0)

print(df)
