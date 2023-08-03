import re

import pandas as pd

from BaseBankStatementReport import BankStatementReport


class SterlingBankStatement(BankStatementReport):

    def __init__(self, pdf_directory):
        super().__init__(pdf_directory)

    def format_account_summary_table(self, reader, table_index=0, page=0):
        # get first table in first page
        summary_tables = reader.pages[page].extract_tables()[table_index]
        table_dictionary = {}
        for item in summary_tables:
            if len(item) >= 2:
                # Convert the key by replacing spaces with underscores and making it lowercase
                key1 = item[0].replace(' ', '_').replace('.', '').replace(':', '').replace('\n', '_').lower()
                # Set the value as the second item in the list
                value1 = item[1].replace('\n', '_')
                table_dictionary[key1] = value1
            if len(item) >= 4:
                # Convert the key by replacing spaces with underscores and making it lowercase
                key2 = item[2].replace(' ', '_').replace('.', '').replace(':', '').replace('\n', '_').lower()
                # Set the value as the second item in the list
                value2 = item[3].replace('\n', '_')
                table_dictionary[key2] = value2

        return table_dictionary

    def get_account_number(self, _formatted_summary_table):
        return _formatted_summary_table['account_number']

    def get_account_name(self, _formatted_summary_table):
        return _formatted_summary_table['customer_name']

    def get_opening_balance(self, _formatted_summary_table):
        return _formatted_summary_table['opening_balance']

    def get_closing_balance(self, _formatted_summary_table):
        return _formatted_summary_table['closing_balance']

    def get_statement_period(self, _formatted_summary_table):
        return {'from_date': _formatted_summary_table['start_date'], 'to_date': _formatted_summary_table['end_date']}

    def get_transactions_table_header_mapping(self):
        return {
            'txn_date': 'Txn Date',
            'val_date': 'Val Date',
            'remarks': 'Remarks',
            'debit': 'Debit',
            'credit': 'Credit',
            'balance': 'Balance'
        }

    def get_transactions_table_headers(self, reader):
        return self.get_transactions_table_header_mapping().values()

    def get_transactions_table_rows(self, reader, page=0):
        date_pattern = r'\d{1,2}-([A-Z]|[a-z]){3}-\d{4}'
        money_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b'
        if page == 0:
            table = reader.pages[page].extract_tables()[4]
            rows_without_header = table[1:]
        else:
            table = reader.pages[page].extract_tables()[0]
            rows_without_header = table[0:]
        modified_rows = []
        # Remove None
        for index, row in enumerate(rows_without_header):
            transaction_date = None
            value_date = None
            credit_or_debit = None
            balance = None
            remark = None

            if balance is not None:
                continue
            for item in row:
                if item is not None and re.match(date_pattern, item):
                    if transaction_date is None:
                        transaction_date = item
                    else:
                        value_date = item
                elif item is not None and re.match(money_pattern, item):
                    if credit_or_debit is None:
                        credit_or_debit = item
                    else:
                        balance = item
                elif item is not None and item.strip() != '-' and item != '' and len(item) >= 5 and re.match(
                        money_pattern, item) is None and re.match(date_pattern, item) is None:
                    remark = item
            if transaction_date is None or value_date is None or credit_or_debit is None or balance is None:
                continue
            modified_rows.append([transaction_date, value_date, remark, credit_or_debit, credit_or_debit, balance])

        for index, row in enumerate(modified_rows):
            # row[5] is balance column
            # row[4] is credit column
            # row[3] is a debit column
            current_row = modified_rows[index]
            previous_row = modified_rows[index - 1]
            current_row_balance = current_row[5]
            previous_row_balance = previous_row[5]

            if current_row[2].find('Opening Balance') != -1 and page == 0:
                current_row_balance = row[3]
                previous_row_balance = row[3]

            current_row_balance = float(current_row_balance.replace(',', ''))
            previous_row_balance = float(previous_row_balance.replace(',', ''))
            if current_row_balance > previous_row_balance:
                row[3] = 0.00
            else:
                row[4] = 0.00
        return modified_rows

    def result(self):
        reader, status, message = self.get_pdf_reader()
        print(message)
        if status == 0:
            raise Exception("Reading of file failed")

        num_pages = len(reader.pages)
        text = self.get_pdf_page_text(reader)
        last_page_text = self.get_pdf_page_text(reader, num_pages - 1)

        cleaned_text = self.clean_text(text)
        formatted_summary_table = self.format_account_summary_table(reader)
        total_withdrawals_extracted = self.get_total_withdrawal(last_page_text)
        total_deposit_extracted = self.get_total_deposit(last_page_text)
        account_name_extracted = self.get_account_name(formatted_summary_table)
        statement_period_extracted = self.get_statement_period(formatted_summary_table)
        account_number_extracted = self.get_account_number(formatted_summary_table)
        opening_balance_extracted = self.get_opening_balance(formatted_summary_table)
        closing_balance_extracted = self.get_closing_balance(formatted_summary_table)

        table_headers = self.get_transactions_table_headers(reader)

        trans_rows = []

        for page_num in range(num_pages):
            try:
                # print(page_num)
                new_rows = self.get_transactions_table_rows(reader, page_num)
                trans_rows.extend(new_rows)
            except Exception as e:
                print(page_num)
                print("from result", e)
        if opening_balance_extracted is None:
            opening_balance_extracted = trans_rows[0][5]

        if closing_balance_extracted is None:
            opening_balance_extracted = trans_rows[len(trans_rows) - 1][5]

        formatted_df = self.format_dataframe_columns(table_headers, table_rows=trans_rows)

        print("--- Predicted Salary List ----")

        salary_df = self.predict_salary_income(formatted_df, table_headers, 50000, 500000)
        print(salary_df)
        average_monthly_balance = self.get_average_monthly_balance(formatted_df)

        return {
            'period': statement_period_extracted,
            "account_name": account_name_extracted,
            "account_number": account_number_extracted,
            "total_turn_over_credit": total_deposit_extracted,
            "total_turn_over_debits": total_withdrawals_extracted,
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
                row['Value Date'],
                row['Description'],
                row['Withdrawals'],
                row['Deposits'],
                row['Balance'],
            ])
        salary_df = pd.DataFrame(potential_salary, columns=table_headers)
        return salary_df


access_bank_statement_pdf_path = "../pdfs/sterling.pdf"

bank_statement = SterlingBankStatement(access_bank_statement_pdf_path)

result = bank_statement.result()
print(result)
exit()
