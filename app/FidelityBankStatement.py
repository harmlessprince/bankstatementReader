import re

import pandas as pd

from BaseBankStatementReport import BankStatementReport


class FidelityBankStatement(BankStatementReport):

    def __init__(self, pdf_directory):
        super().__init__(pdf_directory)

    def get_account_number(self, text):
        pattern = r'Account:\s+(\d{10,12})'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            account_number = match.group(1)
            return account_number
        else:
            return None
        pass

    def get_account_name(self, text):

        pattern = r"(?i)Type:\s+(Savings|Current)\s+(\w+)\s+(\w+)\s+(\w+)"

        match = re.search(pattern, text, re.IGNORECASE)
        full_name = ''
        if match:
            first_name = match.group(2)
            middle_name = match.group(3)
            last_name = match.group(4)

            if first_name is not None:
                full_name = first_name

            if middle_name is not None:
                full_name = full_name + ' ' + middle_name

            if last_name is not None:
                full_name = full_name + ' ' + last_name
            return full_name
        else:
            return None

    def get_total_withdrawal(self, dataframe):
        return dataframe['Withdrawals'].sum()

    def get_total_deposit(self, dataframe):
        return dataframe['Deposits'].sum()

    # def get_opening_balance(self, _formatted_summary_table):
    #     return _formatted_summary_table['opening_balance']

    # def get_closing_balance(self, _formatted_summary_table):
    #     return _formatted_summary_table['closing_balance']

    def get_statement_period(self, text):

        pattern = r"From\s+(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November" \
                  r"|December)\s+\d{4})\s+to\s+(\d{1,2}\s+(" \
                  r"?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            from_date = match.group(1)
            to_date = match.group(2)
            from_date = self.try_multiple_date_formats(from_date)
            from_date = from_date.strftime("%d-%b-%Y")
            to_date = self.try_multiple_date_formats(to_date)
            to_date = to_date.strftime("%d-%b-%Y")
            return {'from_date': from_date, 'to_date': to_date}
        else:
            return {'from_date': None, 'to_date': None}

    def get_transactions_table_header_mapping(self):
        return {
            'transaction_date': 'Transaction Date',
            'value_date': 'Value Date',
            'channel': 'Channel',
            'details': 'Details',
            'pay_in': 'Pay In',
            'pay_out': 'Pay Out',
            'balance': 'Balance'
        }

    def get_transactions_table_headers(self, reader):
        return self.get_transactions_table_header_mapping().values()

    def get_transactions_table_rows(self, reader, page=0):
        date_pattern = r'\d{1,2}-([A-Z]|[a-z]){3}-\d{2}'
        # money_pattern = r'^\d{1,3}(?:,\d{3})*(?:\.\d{2})?$'
        money_pattern = r'^\d{1,3}(?:,\d{3})*(?:\.\d{2})$'
        channels = ["others", "instant banking", 'banking', 'instant', "online banking", 'online', "nip transfer"]
        table = reader.pages[page].extract_tables(
            table_settings={"vertical_strategy": "text", "horizontal_strategy": "lines"})[0]
        rows_without_header = table[0:]
        modified_rows = []
        for index, row in enumerate(rows_without_header):
            if len(row) > 0:
                is_date = re.match(date_pattern, row[0])
                if is_date is None:
                    continue

            transaction_date = None
            value_date = None
            credit_or_debit = None
            balance = None
            channel = ''
            details = ''
            if balance is not None:
                continue

            for item_index, item in enumerate(row):
                item = item.replace('\n', ' ')

                if item is not None and re.match(date_pattern, item):
                    if transaction_date is None:
                        transaction_date = item
                    else:
                        if value_date is None:
                            value_date = item
                if item_index == 2 and item.isdigit() and transaction_date is not None:
                    if re.match(date_pattern, row[1] + row[item_index]) and value_date is None:
                        value_date = row[1] + row[item_index]

                elif item is not None and re.match(money_pattern, item):
                    # print(float(item.replace(',', '')).isdecimal(), item.replace(',', ''))
                    if credit_or_debit is None:
                        credit_or_debit = item
                        # print("credit_or_debit", credit_or_debit)
                    else:
                        balance = item
                elif item.lower() in channels and item is not None:
                    channel = item
                elif item is not None and item.strip() != '-' and item != '' and re.match(
                        money_pattern, item) is None and re.match(date_pattern, item) is None and item.replace('\n',
                                                                                                               '').lower() not in channels:
                    # print(item)
                    details = details + item
            if transaction_date is None or value_date is None or credit_or_debit is None or balance is None:
                continue
            modified_rows.append(
                [transaction_date, value_date, channel, details, credit_or_debit,
                 credit_or_debit, balance])
        for index, row in enumerate(modified_rows):
            # row[6] is balance column
            # row[5] is a debit column
            # row[4] is credit column
            current_row = modified_rows[index]
            previous_row = modified_rows[index - 1]
            current_row_balance = current_row[6]
            previous_row_balance = previous_row[6]

            current_row_balance = float(current_row_balance.replace(',', ''))
            previous_row_balance = float(previous_row_balance.replace(',', ''))
            if current_row_balance > previous_row_balance:
                row[5] = 0.00
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
        cleaned_text = self.clean_text(text)
        last_page_text = self.get_pdf_page_text(reader, num_pages - 1)
        account_name_extracted = self.get_account_name(cleaned_text)
        account_number_extracted = self.get_account_number(cleaned_text)
        statement_period_extracted = self.get_statement_period(cleaned_text)
        opening_balance_extracted = self.get_opening_balance(cleaned_text)
        closing_balance_extracted = self.get_closing_balance(last_page_text)
        table_headers = self.get_transactions_table_headers(reader)
        trans_rows = []

        for page_num in range(num_pages):
            try:
                new_rows = self.get_transactions_table_rows(reader, page_num)
                trans_rows.extend(new_rows)
            except Exception as e:
                print(page_num)
                print("from result", e)

        if opening_balance_extracted is None:
            opening_balance_extracted = trans_rows[0][6]

        if closing_balance_extracted is None:
            opening_balance_extracted = trans_rows[len(trans_rows) - 1][6]
        # print(trans_rows)
        # exit()
        formatted_df = self.format_dataframe_columns(table_headers, table_rows=trans_rows)
        formatted_df_copy = formatted_df.copy()
        total_withdrawals_extracted = self.get_total_withdrawal(formatted_df_copy)
        total_deposit_extracted = self.get_total_deposit(formatted_df_copy)
        print("--- Predicted Salary List ----")
        salary_df = self.predict_salary_income(formatted_df_copy, table_headers, 50000, 500000)

        average_monthly_balance = self.get_average_monthly_balance(formatted_df_copy)
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
                row['Channel'],
                row['Description'],
                row['Deposits'],
                row['Withdrawals'],
                row['Balance'],
            ])
        salary_df = pd.DataFrame(potential_salary, columns=table_headers)
        return salary_df


access_bank_statement_pdf_path = "../pdfs/fidelity.pdf"

bank_statement = FidelityBankStatement(access_bank_statement_pdf_path)

result = bank_statement.result()
print(result)
exit()
