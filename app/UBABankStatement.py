from datetime import datetime
from BaseBankStatementReport import BankStatementReport
import pandas as pd
import re


class UBABankStatement(BankStatementReport):
    def predict_salary_income(self, dataframe, table_headers, lower_bound, upper_bound):
        # Filter the DataFrame to get rows with values within the specified range
        filtered_df = dataframe[(dataframe['Deposits'] >= lower_bound) & (dataframe['Deposits'] <= upper_bound)]
        potential_salary = []
        # Loop through each unique value and find occurrences
        for index, row in filtered_df.iterrows():
            unique = self.is_unique_amount_in_month_year(row, filtered_df)
            if not unique:
                continue
            potential_salary.append([
                row['Transaction Date'],
                row['Value Date'],
                row['Description'],
                row['Chq No'],
                row['Withdrawals'],
                row['Deposits'],
                row['Balance'],
            ])
        salary_df = pd.DataFrame(potential_salary, columns=table_headers)
        return salary_df

    # matches 'September 28th 2022'
    first_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November' \
                    r'|December)\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}\b'
    # matches October 2nd October 1st 2022 2022
    second_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November' \
                     r'|December)\s+\d{1,2}(?:st|nd|rd|th)\s+(' \
                     r'?:January|February|March|April|May|June|July|August|September|October|November' \
                     r'|December)\s+\d{1,2}(?:st|nd|rd|th)\s+\d{4}\s+\d{4}\b'

    def __init__(self, pdf_directory):
        super().__init__(pdf_directory)

    def clean_date_v2(self, date_str, _format="%Y-%m-%d"):
        try:
            return pd.to_datetime(date_str, format=_format)
        except ValueError as err:
            print(err)
            print('clean_date_v2:', date_str)
            # return date_str

    def get_account_name(self, text):
        full_name = super().get_account_name(text)
        if full_name is not None:
            return full_name
        pattern = r"(?i)BANK\s+STATEMENT\s+(\w+)\s+(\w+)\s+(\w+)"
        match = re.search(pattern, text, re.IGNORECASE)

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

    def get_total_withdrawal(self, text):
        total_withdrawals = super().get_total_withdrawal(text)
        if total_withdrawals is not None:
            return total_withdrawals
        pattern = r'Credits[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            total_withdrawals = match.group(1)
            return total_withdrawals
        else:
            return None

    def get_total_deposit(self, text):
        total_deposit = super().get_total_deposit(text)
        if total_deposit is not None:
            return total_deposit
        pattern = r'Debits[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            total_deposit = match.group(1)
            return total_deposit
        else:
            return None

    def get_transactions_table_headers(self, reader):
        tables = reader.pages[0].extract_tables()
        if len(tables) > 0:
            table = tables[1]
            headers = table[0]
            header_mapping = self.get_transactions_table_header_mapping()
            header_columns = [header_mapping[col.replace('\n', ' ').lower().replace(' ', '_').replace('.', '').strip()]
                              for col in headers if col is not None]
            return header_columns
        else:
            return [
                'Trans Date',
                'Value Date',
                'Narration',
                'Chq No',
                'Debit',
                'Credit',
                'Balance'
            ]

    def get_transactions_table_rows(self, reader, page):
        first_table_format = reader.pages[page].extract_tables()
        second_table_format = reader.pages[page].extract_tables(
            table_settings={"vertical_strategy": "text", "horizontal_strategy": "lines"})
        rows_with_errors = []
        if len(first_table_format) > 0:
            # this works for uba 1 sample file
            tables = first_table_format
            if page == 0:
                table = tables[1]
                rows_without_header = table[1:]
            else:
                table = reader.pages[page].extract_tables()[0]
                rows_without_header = table[1:]
            return rows_without_header
        elif len(second_table_format) > 0:
            # this works for uba2 sample file
            tables = second_table_format
            rows = tables[0]
            new_trans_rows = []
            for row in rows:
                if len(row) < 7:
                    continue
                try:
                    if page == 0:
                        trans_date = row[0].replace('\n', ' ')
                        value_date = row[1].replace('\n', ' ' + row[2] + ' ')
                        row[0] = trans_date
                        row[1] = value_date
                        row.pop(2)
                    else:
                        trans_date = row[0].replace('\n', ' ' + row[1] + ' ')
                        value_date = row[2].replace('\n', ' ' + row[3] + ' ')
                        if re.match(self.first_pattern, trans_date) is None and re.match(self.second_pattern,
                                                                                         trans_date) is None:
                            continue
                        if re.match(self.first_pattern, value_date) is None and re.match(self.second_pattern,
                                                                                         value_date) is None:
                            continue
                        row[0] = trans_date
                        row[2] = value_date
                        row[3] = row[4]  # row 3 is narration
                        row.pop(1)
                        row.pop(3)
                    # Convert the input string to a datetime object

                    row[0] = self.custom_date_format(row[0])
                    row[1] = self.custom_date_format(row[1])
                    if len(row) == len(self.get_transactions_table_header_mapping()):
                        new_trans_rows.append(row)
                except Exception as ex:
                    rows_with_errors.append(row)
                    print("here:", ex)
                    print(row)
                    print("page:", page)
            return new_trans_rows
        else:
            return []

    # formats date in this format  "December 2nd 2022"
    def custom_date_format(self, date_str):
        try:

            if re.match(self.first_pattern, date_str):
                date_str = date_str

            if re.match(self.second_pattern, date_str):
                split_date_str = date_str.replace('\n', ' ').split()
                date_str = split_date_str[0] + ' ' + split_date_str[1] + ' ' + split_date_str[len(split_date_str) - 1]

            # Remove the suffix from the day part
            day_str = date_str.split(' ')[1].rstrip('nd').rstrip('st').rstrip('rd').rstrip('th')
            date_str_without_suffix = f"{date_str.split(' ')[0]} {day_str} {date_str.split(' ')[2]}"

            # Convert the input string to a datetime object
            date_obj = datetime.strptime(date_str_without_suffix, "%B %d %Y")

            # Format the datetime object to your desired output format
            formatted_date = date_obj.strftime("%Y-%m-%d")
            return formatted_date
        except Exception as custom_date_e:
            print("custom_date_format: ", custom_date_e)
            print("date string: ", date_str)
            raise ValueError("Date does not match  any of the patterns")

    def get_transactions_table_header_mapping(self):
        return {
            'trans_date': 'Trans Date',
            'value_date': 'Value Date',
            'narration': 'Narration',
            'chq_no': 'Chq No',
            'debit': 'Debit',  # money withdrawn from account
            'credit': 'Credit',  # money sent to account
            'balance': 'Balance',
        }

    def get_statement_period(self, text):
        parent_period = super().get_statement_period(text)
        if parent_period.get('from_date') is not None and parent_period.get('to_date') is not None:
            return parent_period

        from_date_pattern = r'Transaction Date From[:.]?\s*(\b(?:January|February|March|April|May|June|July|August' \
                            r'|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}\b)'

        to_date_pattern = r'Transaction Date To[:.]?\s*(\b(?:January|February|March|April|May|June|July|August' \
                          r'|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4}\b)'

        match = re.search(from_date_pattern, text, re.IGNORECASE)
        if re.search(from_date_pattern, text, re.IGNORECASE):
            from_date = match.group(1)
            from_date = self.custom_date_format(from_date)
        else:
            from_date = None

        if re.search(to_date_pattern, text, re.IGNORECASE):
            to_date = match.group(1)
            to_date = self.custom_date_format(to_date)
        else:
            to_date = None
        return {'from_date': from_date, 'to_date': to_date}

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
                new_rows = bank_statement.get_transactions_table_rows(reader, page_num)
                trans_rows.extend(new_rows)
            except Exception as e:
                print(e)

        if opening_balance_extracted is None:
            opening_balance_extracted = trans_rows[0][6]

        if closing_balance_extracted is None:
            closing_balance_extracted = trans_rows[len(trans_rows) - 1][6]

        df = self.format_dataframe_columns(table_headers, table_rows=trans_rows)
        print("--- Predicted Salary List ----")
        salary_df = self.predict_salary_income(df, table_headers, 10000, 300000)
        print(salary_df)
        average_monthly_balance = self.get_average_monthly_balance(df)
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


pdf_path = "../pdfs/uba3.pdf"

bank_statement = UBABankStatement(pdf_path)

result = bank_statement.result()

print(result)
