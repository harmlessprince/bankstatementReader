import pandas as pd
from BaseBankStatementReport import BankStatementReport
from abc import ABC, abstractmethod
import re
from datetime import datetime


class AccessBankStatement(BankStatementReport):

    def __init__(self, pdf_directory):
        super().__init__(pdf_directory)

    def get_transactions_table_header_mapping(self):
        return {
            'date': 'Date',
            'transaction_details': 'Transaction Details',
            'reference': 'Reference',
            'value_date': 'Value Date',
            'withdrawals': 'Withdrawals',
            'lodgements': 'Lodgements',
            'balance': 'Balance'
        }

    def get_transactions_table_headers(self, reader):
        return [
            'Date',
            'Transaction Details',
            'Reference',
            'Value Date',
            'Withdrawals',
            'Lodgements',
            'Balance'
        ]
        # table = reader.pages[0].extract_tables()[1]
        # access_table_headers = table[1]
        # header_mapping = self.get_transactions_table_header_mapping()
        # header_columns = [header_mapping[col.replace('\n', ' ').lower().replace(' ', '_').replace('.', '').strip()]
        #                   for col in access_table_headers if col is not None]
        # return header_columns

    def pad_header_with_unknown(self, rows, headers):
        if len(rows[0]) > len(headers):
            # Index of "Value Date" in the list
            value_date_index = headers.index('Value Date')
            headers.pop(value_date_index - 1)
            # # Insert the new item before "Value Date"
            # headers.insert(value_date_index, unknown)
            return headers

        else:
            return headers

    def get_transactions_table_rows(self, reader, page=0):
        if page == 0:
            table = reader.pages[page].extract_tables()[1]
            rows_without_header = table[2:]
        else:
            table = reader.pages[page].extract_tables()[0]
            rows_without_header = table[1:]
        modified_rows = [[item.replace('\n', '').strip() if item else '' for item in row] for row in
                         rows_without_header]
        new_trans_rows = []
        pattern = r"\d{1,2}-[A-Z]{3}-\d{4}"
        second_pattern = r"\d{1,2}-[A-Z]{3}-\d{2}"
        for row in modified_rows:
            if page == 0:
                trans_date = row[0]
                value_date = row[4]
                row.pop(3)
            else:
                trans_date = row[0]
                value_date = row[3]
            if re.match(pattern, trans_date) is None:
                continue
            if re.match(second_pattern, value_date) is None:
                continue
            new_trans_rows.append(row)

        return new_trans_rows

    def result(self):
        reader, status, message = self.get_pdf_reader()
        print(message)
        if status == 0:
            raise Exception("Reading of file failed")

        text = self.get_pdf_page_text(reader)
        cleaned_text = self.clean_text(text)

        account_name_extracted = self.get_account_name(cleaned_text)
        statement_period_extracted = self.get_statement_period(cleaned_text)
        account_number_extracted = self.get_account_number(cleaned_text)
        total_withdrawals_extracted = self.get_total_withdrawal(cleaned_text)
        total_deposit_extracted = self.get_total_deposit(cleaned_text)
        opening_balance_extracted = self.get_opening_balance(cleaned_text)
        closing_balance_extracted = self.get_closing_balance(cleaned_text)

        table_headers = self.get_transactions_table_headers(reader)

        num_pages = len(reader.pages)
        trans_rows = []
        for page_num in range(num_pages):
            try:
                # print(page_num)
                new_rows = self.get_transactions_table_rows(reader, page_num)
                if page_num == 0:
                    self.pad_header_with_unknown(new_rows, table_headers)
                trans_rows.extend(new_rows)
            except Exception as e:
                print(page_num)
                print("from result", e)

        if opening_balance_extracted is None:
            opening_balance_extracted = trans_rows[0][6]

        if closing_balance_extracted is None:
            opening_balance_extracted = trans_rows[len(trans_rows) - 1][6]
        formatted_df = self.format_dataframe_columns(table_headers, table_rows=trans_rows)

        print("--- Predicted Salary List ----")

        salary_df = self.predict_salary_income(formatted_df, table_headers, 50000, 500000)

        average_monthly_balance = self.get_average_monthly_balance(formatted_df)
        self.export_to_excel(
            dataframe=formatted_df,
            name=account_name_extracted,
            start_date=statement_period_extracted.get('from_date'),
            end_date=statement_period_extracted.get('to_date')
        )
        return {
            'period': statement_period_extracted,
            "account_name": account_name_extracted,
            "account_number": account_number_extracted,
            "total_turn_over_credit": float(total_deposit_extracted.replace(',', '')),
            "total_turn_over_debits": float(total_withdrawals_extracted.replace(',', '')),
            "opening_balance": opening_balance_extracted,
            "closing_balance": closing_balance_extracted,
            "average_monthly_balance": average_monthly_balance
        }

    def predict_salary_income(self, dataframe, table_headers, lower_bound, upper_bound):
        # Filter the DataFrame to get rows with values within the specified range
        filtered_df = dataframe[(dataframe['Deposits'] >= lower_bound) & (dataframe['Deposits'] <= upper_bound)]
        potential_salary = []
        for index, row in filtered_df.iterrows():
            unique = self.is_unique_amount_in_month_year(row, filtered_df)
            if not unique:
                continue
            potential_salary.append([
                row['Transaction Date'],
                row['Description'],
                row['Reference'],
                row['Value Date'],
                row['Withdrawals'],
                row['Deposits'],
                row['Balance'],
            ])
        salary_df = pd.DataFrame(potential_salary, columns=table_headers)
        return salary_df


access_bank_statement_pdf_path = "/Users/harmlessprince/python/pdfconverter/pdfs/access.pdf"

bank_statement = AccessBankStatement(access_bank_statement_pdf_path)

result = bank_statement.result()
print(result)
exit()
