from BaseBankStatementReport import BankStatementReport
import pandas as pd
import re


class ZenithBankStatement(BankStatementReport):

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

    def result(self):
        reader, status, message = self.get_pdf_reader()
        print(message)
        if status == 0:
            raise Exception("Reading of file failed")
        text = self.get_pdf_page_text(reader)
        cleaned_text = self.clean_text(text)

        statement_period_extracted = bank_statement.get_statement_period(cleaned_text)
        account_name_extracted = bank_statement.get_account_name(cleaned_text)
        account_number_extracted = bank_statement.get_account_number(cleaned_text)
        total_withdrawals_extracted = bank_statement.get_total_withdrawal(cleaned_text)
        total_deposit_extracted = bank_statement.get_total_deposit(cleaned_text)
        opening_balance_extracted = bank_statement.get_opening_balance(cleaned_text)
        closing_balance_extracted = bank_statement.get_closing_balance(cleaned_text)

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
        # print(self.categorize_salary(salary_df, 'Description'))
        print(salary_df)
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

    def __init__(self, pdf_directory):
        super().__init__(pdf_directory)

    def get_account_number(self, text):
        pattern = r'Account\s+(?:No(?:\.|:)?|Number(?:\.|:)?)\s+SA\s+(\d{10,12})'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            account_number = match.group(1)
            return account_number
        else:
            return None

    def get_account_name(self, text):

        pattern = r"(?i)(\w+)\s+(\w+)\s+(\w+)\s+Account\s+Number:"

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
        return [
            'Date Posted',
            'Value Date',
            'Description',
            'Debit',
            'Credit',
            'Balance'
        ]

    def add_pipe_to_money(self, text):
        # Define a regular expression to find strings that look like money (e.g., 76.29, 3,176.29, 76.29)
        # Define a regular expression to find occurrences of the pattern "date date amount amount"
        date_pattern = r'\d{2}/\d{2}/\d{4}'
        money_pattern = r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?'

        full_pattern = rf'{date_pattern}\s{date_pattern}\s{money_pattern}\s{money_pattern}'

        # Use regex to find all occurrences of the money pattern in the text
        matches = re.findall(full_pattern, text)

        # Iterate through the matches and add a pipe at the end of each match
        for match in matches:
            text = text.replace(match, match + ' |')

        return text

    def insert_pipe_after_opening_balance(self, input_string):
        # Define the regular expression pattern for money
        money_pattern = r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?'

        # Define the regular expression pattern for "Opening Balance" followed by money
        opening_balance_pattern = r'OPENING BALANCE\s+(' + money_pattern + ')'

        # Search for the pattern in the input string
        match = re.search(opening_balance_pattern, input_string)

        # If the pattern is found, insert a pipe "|" at the front of the money pattern
        if match:
            modified_string = input_string[:match.start(1)] + match.group(1) + ' | ' + input_string[match.end(1):]
            return modified_string
        else:
            return input_string

    def find_entries_after_header(self, data_string, header):
        data_lines = data_string.split('\n')
        header_index = None

        for i, line in enumerate(data_lines):
            if header in line:
                header_index = i
                break

        if header_index is not None:
            return '\n'.join(data_lines[header_index + 1:])
        else:
            return ""

    def extract_patterns(self, input_string):
        try:
            # Define the regular expression patterns
            date_pattern = r'\d{2}/\d{2}/\d{4}'
            money_pattern = r'[\d,]+\.\d{2}'

            # Find the first and second date strings
            dates = re.findall(date_pattern, input_string)
            first_date_str, second_date_str = dates[0], dates[1]

            # Find the money pattern(s)
            money_patterns = re.findall(money_pattern, input_string)

            # Remove the money patterns and dates from the input string
            remaining_string = re.sub(date_pattern, '', input_string)
            remaining_string = re.sub(money_pattern, '', remaining_string).strip()

            return [first_date_str, second_date_str, money_patterns, remaining_string]
        except Exception as e:
            print("Extract Pattern method: ", e)

    def get_transactions_table_rows(self, reader, page):
        header_to_find = "DATE POSTED VALUE DATE DESCRIPTION DEBIT CREDIT BALANCE"
        text = reader.pages[page].extract_text()
        date_pattern = r'\d{2}/\d{2}/\d{4}'
        money_pattern = r'[\d,]+\.\d{2}'
        rows_without_header = []
        split_balance_opening_balance = 0
        if page == 0:
            extracted_text = self.find_entries_after_header(text, header_to_find)
            extracted_text = self.insert_pipe_after_opening_balance(extracted_text)
        else:
            extracted_text = self.find_entries_after_header(text, header_to_find)

        extracted_text = self.add_pipe_to_money(extracted_text)
        # print(extracted_text)
        split_extracted_text = extracted_text.split('|')
        # something = split_extracted_text[len(split_extracted_text) - 3].replace('\n', ' ')
        for item in split_extracted_text:
            if not (item.find('OPENING BALANCE') != -1):
                cleaned_item = item.replace('\n', '|')

                list_of_cleaned_item = cleaned_item.split(' ')
                list_of_cleaned_item = self.remove_empty_and_none(list_of_cleaned_item)

                length_of_list_of_cleaned_item = len(list_of_cleaned_item)
                balance = list_of_cleaned_item[length_of_list_of_cleaned_item - 1]
                credit_or_debit = list_of_cleaned_item[length_of_list_of_cleaned_item - 2]
                value_date = list_of_cleaned_item[length_of_list_of_cleaned_item - 3]
                date_posted = list_of_cleaned_item[length_of_list_of_cleaned_item - 4]

                description = ''.join(list_of_cleaned_item[0: len(list_of_cleaned_item) - 4])
                alternative_item = self.extract_patterns(item)
                alternative_credit_or_debit = ''
                alternative_item_balance = ''
                if alternative_item is not None:
                    money_patterns = alternative_item[2]
                    if len(money_patterns) == 2:
                        # print(alternative_credit_or_debit)
                        alternative_item_balance = money_patterns[1]
                        alternative_credit_or_debit = money_patterns[0]
                    alternative_value_date = alternative_item[1]
                    alternative_date_posted = alternative_item[0]
                    # print(alternative_item)
                    alternative_item_description = alternative_item[3]

                if re.match(date_pattern, date_posted) is None and re.match(date_pattern, alternative_date_posted):
                    date_posted = alternative_date_posted

                if re.match(date_pattern, value_date) is None and re.match(date_pattern, alternative_value_date):
                    value_date = alternative_value_date
                    # description = alternative_item_description

                if re.match(money_pattern, balance) is None and re.match(money_pattern, alternative_item_balance):
                    balance = alternative_item_balance

                if re.match(money_pattern, credit_or_debit) is None and alternative_credit_or_debit is not None:
                    if re.match(money_pattern, alternative_credit_or_debit):
                        credit_or_debit = alternative_credit_or_debit
                date_posted_is_valid = re.match(date_pattern, date_posted)
                value_date_is_valid = re.match(date_pattern, value_date)
                credit_or_debit_is_valid = re.match(money_pattern, balance)
                if date_posted_is_valid and value_date_is_valid and credit_or_debit_is_valid:
                    row = [date_posted, value_date, description, credit_or_debit, credit_or_debit, balance]
                    rows_without_header.append(row)
                else:
                    continue
            else:
                split_balance_opening_balance = item.split(' ')[2]
                row = [None, None, 'Opening Balance', 0.00, 0.00, split_balance_opening_balance]
                # rows_without_header.append(row)

        for index, row in enumerate(rows_without_header):
            # row[5] is balance
            # row[4] is credit|deposit
            # row[3] is balance
            current_row = rows_without_header[index]
            previous_row = rows_without_header[index - 1]
            current_row_balance = current_row[5]
            previous_row_balance = previous_row[5]

            # if index != 0:
            current_row_balance = float(current_row_balance.replace(',', ''))
            previous_row_balance = float(previous_row_balance.replace(',', ''))
            if current_row_balance > previous_row_balance:
                row[3] = 0.00
            else:
                row[4] = 0.00

        # else:
        #     if float(split_balance_opening_balance) > 0:
        #         row[3] = 0.00
        #         row[4] = 0.00
        # print(rows_without_header)
        # exit()
        return rows_without_header

    def remove_empty_and_none(self, input_list):
        return [item for item in input_list if item is not None and item != ""]

    def get_transactions_table_header_mapping(self):
        return {
            'date_posted': 'Date Posted',
            'value_date': 'Value Date',
            'description': 'Description',
            'debit': 'Debit',
            'credit': 'Credit',
            'balance': 'Balance'
        }


pdf_path = "/Users/harmlessprince/python/pdfconverter/pdfs/zenith.pdf"

bank_statement = ZenithBankStatement(pdf_path)

print(bank_statement.result())
