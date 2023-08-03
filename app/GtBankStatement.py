from BaseBankStatementReport import BankStatementReport
import pandas as pd
import re


class GtBankStatement(BankStatementReport):

    def __init__(self, pdf_directory):
        if pdf_directory is None or pdf_directory == '':
            pdf_directory = "../pdfs/gt.pdf"
        super().__init__(pdf_directory)

    def get_account_number(self, _formatted_summary_table):
        return _formatted_summary_table['account_no']

    def get_total_withdrawal(self, _formatted_summary_table):
        return _formatted_summary_table['total_debit']

    def get_total_deposit(self, _formatted_summary_table):
        return _formatted_summary_table['total_credit']

    def get_opening_balance(self, _formatted_summary_table):
        return _formatted_summary_table['opening_balance']

    def get_closing_balance(self, _formatted_summary_table):
        return _formatted_summary_table['closing_balance']

    def get_account_name(self, text):

        pattern = r"(?i)CUSTOMER\s+STATEMENT\s+(\w+)\s+(\w+)\s+(\w+)"

        match = re.search(pattern, text, re.IGNORECASE)
        full_name = ''
        if match:
            first_name = match.group(1)
            middle_name = match.group(2)
            last_name = match.group(3)

            if first_name is not None:
                full_name = first_name

            if middle_name is not None:
                full_name = full_name + ' ' + middle_name

            if last_name is not None:
                full_name = full_name + ' ' + last_name
            return full_name
        else:
            return None

    def get_transactions_table_headers(self, reader):

        table = reader.pages[0].extract_tables()[1]
        headers = table[0]
        header_mapping = self.get_transactions_table_header_mapping()
        header_columns = [header_mapping[col.replace('\n', ' ').lower().replace(' ', '_').replace('.', '').strip()]
                          for col in headers if col is not None]
        return header_columns

    def get_transactions_table_rows(self, reader, page):
        date_pattern = r'\d{1,2}-([A-Z]|[a-z]){3}-\d{4}'
        if page == 0:
            table = reader.pages[page].extract_tables()[1]
            rows_without_header = table[1:]
        else:
            table = reader.pages[page].extract_tables()[0]
            rows_without_header = table[0:]
        trans_rows = []
        for row in rows_without_header:
            trans_date = row[0]
            # value_date = row[1]
            if re.match(date_pattern, trans_date) is None:
                continue
            trans_rows.append(row)
        return trans_rows

    def get_transactions_table_header_mapping(self):
        return {
            'trans_date': 'Trans Date',
            'remarks': 'Remarks',
            'reference': 'Reference',
            'value_date': 'Value Date',
            'debits': 'Debits',
            'credits': 'Credits',
            'balance': 'Balance',
            'originating_branch': 'Originating Branch',
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
                row['Reference'],
                row['Withdrawals'],
                row['Deposits'],
                row['Balance'],
                row['Originating Branch'],
                row['Description'],
            ])
        salary_df = pd.DataFrame(potential_salary, columns=table_headers)
        return salary_df

    # def format_dataframe_columns(self, table_headers, table_rows):
    #     if len(table_headers) > 0 and len(table_rows) > 0:
    #         df = pd.DataFrame(table_rows, columns=table_headers)
    #         self.rename_column(df, 'Debits', 'Withdrawals')
    #         self.rename_column(df, 'Credits', 'Deposits')
    #         self.rename_column(df, 'Trans Date', 'Transaction Date')
    #
    #         df['Transaction Date'] = df['Transaction Date'].apply(self.try_multiple_date_formats)
    #         df['Value Date'] = df['Value Date'].apply(self.try_multiple_date_formats)
    #         # df['Value Date'] = df['Value Date'].apply(bank_statement.clean_date_v2, format='%d-%b-%Y')
    #         df['Withdrawals'] = self.clean_money('Withdrawals', df)
    #         df['Balance'] = self.clean_money('Balance', df)
    #         df['Deposits'] = self.clean_money('Deposits', df)
    #         df['Remarks'] = self.clean_column(df, 'Remarks')
    #
    #         # Replace NaT values with a custom string, e.g., 'Not Available'
    #
    #         df['Value Date'] = df['Value Date'].fillna('Invalid Date')
    #         df['Transaction Date'] = df['Transaction Date'].fillna('Invalid Date')
    #         df['Withdrawals'] = df['Withdrawals'].fillna(0)
    #         df['Deposits'] = df['Deposits'].fillna(0)
    #         df['Balance'] = df['Balance'].fillna(0)
    #     return df

    def result(self):
        reader, status, message = self.get_pdf_reader()
        print(message)
        if status == 0:
            raise Exception("Reading of file failed")

        text = self.get_pdf_page_text(reader)
        cleaned_text = self.clean_text(text)
        formatted_summary_table = self.format_account_summary_table(reader)
        statement_period_extracted = self.get_statement_period(cleaned_text)
        account_name_extracted = self.get_account_name(cleaned_text)
        account_number_extracted = self.get_account_number(formatted_summary_table)
        total_withdrawals_extracted = self.get_total_withdrawal(formatted_summary_table)
        total_deposit_extracted = self.get_total_deposit(formatted_summary_table)
        opening_balance_extracted = self.get_opening_balance(formatted_summary_table)
        closing_balance_extracted = self.get_closing_balance(formatted_summary_table)

        table_headers = self.get_transactions_table_headers(reader)

        num_pages = len(reader.pages)
        trans_rows = []
        for page_num in range(num_pages):
            try:
                new_rows = self.get_transactions_table_rows(reader, page_num)
                trans_rows.extend(new_rows)
            except Exception as e:
                print(page_num)
                print("from result", e)
        if opening_balance_extracted is None:
            opening_balance_extracted = trans_rows[0][5]

        if closing_balance_extracted is None:
            closing_balance_extracted = trans_rows[len(trans_rows) - 1][5]
        formatted_df = self.format_dataframe_columns(table_headers, table_rows=trans_rows)

        print("--- Predicted Salary List ----")

        salary_df = self.predict_salary_income(formatted_df, table_headers, 50000, 500000)
        print(self.categorize_salary(salary_df, 'Remarks'))
        # print(salary_df)
        average_monthly_balance = self.get_average_monthly_balance(formatted_df)
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

# if __name__ == "__main__":
#     print("Called")
#     pdf_path = "../pdfs/gt.pdf"
#
#     bank_statement = GtBankStatement(pdf_path)
#     result = bank_statement.result()
#     print(result)
#     exit()
