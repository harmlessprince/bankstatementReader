from abc import ABC, abstractmethod

import pdfminer
import pdfplumber as pdfReader
import re
from datetime import datetime
import pandas as pd


class BankStatementReport:
    pdf_directory = ''
    password = None,
    TRANSACTION_DATE_NAME = 'Transaction Date'
    VALUE_DATE_COLUMN_NAME = 'Value Date'
    DEPOSIT_COLUMN_NAME = 'Deposits'
    WITHDRAWAL_COLUMN_NAME = 'Withdrawals'
    DESCRIPTION_COLUMN_NAME = 'Description'

    date_formats = [
        "%Y-%m-%d",  # "2022-11-28"
        "%d/%m/%Y",  # "11/01/2023"
        "%d-%b-%y",  # "01-FEB-23"
        "%d-%b-%Y",
        "%B %d %Y",
        "%Y-%m-%dT%H:%M:%S",  # ISO format with time
        "%Y-%m-%d",  # ISO format without time
        "%m/%d/%Y",  # Month/Day/Year
        "%m/%d/%y",  # Month/Day/Year (short year)
        "%d-%m-%Y",  # Day-Month-Year
        "%Y%m%d",  # Basic ISO format without separators
        "%d/%m/%Y",  # Day/Month/Year
        "%d/%m/%y",  # Day/Month/Year (short year)
        "%b %d, %Y",  # Month abbreviation Day, Year (e.g., Jan 01, 2023)
        "%B %d, %Y",  # Month full name Day, Year (e.g., January 01, 2023)
        "%d %b %Y",  # Day Month abbreviation Year (e.g., 01 Jan 2023)
        "%d %B %Y",  # Day Month full name Year (e.g., 01 January 2023)
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds and Zulu timezone
        "%Y/%m/%d",  # Year/Month/Day
        "%Y.%m.%d",  # Year.Month.Day
        "%d.%m.%Y",  # Day.Month.Year
        "%Y.%m.%d %H:%M:%S",  # Year.Month.Day Hour:Minute:Second
        "%d.%m.%Y %H:%M:%S",  # Day.Month.Year Hour:Minute:Second
    ]

    def __init__(self, pdf_directory, password=None):
        self.pdf_directory = pdf_directory
        self.password = password

    def clean_date(self, column_name, dataframe, format='%d-%b-%Y'):
        return pd.to_datetime(dataframe[column_name], format=format, errors='coerce')

    def try_multiple_date_formats(self, date_string):
        if date_string is None or date_string == '':
            return date_string
        for date_format in self.date_formats:
            try:
                parsed_date = datetime.strptime(date_string.strip(), date_format)
                return parsed_date
            except ValueError:
                continue
        print("date_string: ", date_string)
        # If no format matches, raise an exception or return None as needed.
        raise ValueError("Failed to parse the date using any of the given formats.")

    def clean_money(self, column_name, dataframe):
        return pd.to_numeric(dataframe[column_name].str.replace(',', ''), errors='coerce')

    def rename_column(self, data_frame, formal, new):
        data_frame.rename(columns={formal: new}, inplace=True)

    def clean_column(self, data_frame, column, to_replace='\n', value=' '):
        return data_frame[column].replace(to_replace, value, regex=True)

    def clean_text(self, text):
        # Remove \n and \t characters using regular expressions

        cleaned_text = re.sub(r'\n', ' ', text)
        cleaned_text = re.sub(r'\t', ' ', cleaned_text)

        # Remove extra whitespaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

        return cleaned_text

    def get_pdf_reader(self):
        status = 0
        reader = None
        try:
            reader = pdfReader.open(self.pdf_directory, password=self.password)
            message = 'File loaded successfully!!!!!!'
            status = 1
        except pdfminer.pdfdocument.PDFPasswordIncorrect:
            message = "Please provide a valid password"
        except FileNotFoundError:
            message = "File could not be found"
        except FileExistsError:
            message = "File does not exist"

        return reader, status, message

    def get_statement_period(self, text):
        # matches 01/10/2022 TO 18/01/2023 on zenith sample
        first_pattern = r"(\b\d{2}/\d{2}/\d{4}\b)\s+TO\s+(\b\d{2}/\d{2}/\d{4}\b)"
        # matches "01-Apr-2023 to 30-Jun-2023" on uba, access sample
        second_pattern = r"(\b\d{2}-\w{3}-\d{4}\b)\s+to\s+(\b\d{2}-\w{3}-\d{4}\b)"
        third_pattern = r"(\b\d{2}-\w{3,}-\d{4}\b)\s+to\s+(\b\d{2}-\w{3,}-\d{4}\b)"

        patterns = [first_pattern, second_pattern, third_pattern]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                from_date = match.group(1)
                to_date = match.group(2)
                try:
                    output_format = "%d-%b-%Y"
                    from_date = self.try_multiple_date_formats(from_date)
                    from_date = from_date.strftime(output_format)
                    to_date = self.try_multiple_date_formats(to_date)
                    to_date = to_date.strftime(output_format)
                    return {'from_date': from_date, 'to_date': to_date}
                except Exception as e:
                    print("Statement Period Error", e)
                finally:
                    return {'from_date': from_date, 'to_date': to_date}
            else:
                continue

        return {'from_date': None, 'to_date': None}

    def format_account_summary_table(self, reader, table_index=0, page=0):
        # get first table in first page
        table = reader.pages[page].extract_tables()[table_index]

        table_dictionary = {}
        for item in table:
            if len(item) >= 2:
                # Convert the key by replacing spaces with underscores and making it lowercase
                key = item[0].replace(' ', '_').replace('.', '').replace(':', '').replace('\n', '_').lower()
                # Set the value as the second item in the list
                value = item[1]
                table_dictionary[key] = value
        return table_dictionary

    def get_pdf_page_text(self, reader, page=0):
        return reader.pages[page].extract_text()

    def get_pdf_page_tables(self, reader, page=0):
        return reader.pages[page].extract_tables()

    def get_account_name(self, text=None):
        pattern = r"(?i)Account\s+Name\s*[:.]\s*([a-zA-Z\s]+)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            account_name = match.group(1)
            if account_name is not None:
                # Split the string by spaces
                words = account_name.split()
                # Take the first 3 words and join them back into a single string
                account_name = ' '.join(words[:3])
            return account_name
        else:
            return None

    def get_account_number(self, text):
        pattern = r'Account\s+(?:No(?:\.|:)?|Number(?:\.|:)?)\s+(\d{10,12})'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            account_number = match.group(1)
            return account_number
        else:
            return None
        pass

    def get_opening_balance(self, text):
        pattern = r'Opening Balance[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            opening_balance = match.group(1)
            return opening_balance
        else:
            return None

    def get_closing_balance(self, text):
        pattern = r'Closing Balance[:.]?\s*(-?[\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            closing_balance = match.group(1)
            return closing_balance
        else:
            return None

    @abstractmethod
    def get_transactions_table_headers(self, reader):
        pass

    @abstractmethod
    def get_transactions_table_rows(self, reader, page):
        pass

    @abstractmethod
    def get_transactions_table_header_mapping(self):
        pass

    def get_total_deposit(self, text):
        pattern = r'Total (?:Deposits|Credits|Credit|Lodgements)(?::)?\s*([\d,.]+)'

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            total_deposit = match.group(1)
            return total_deposit
        else:
            return None

    def get_total_withdrawal(self, text):
        pattern = r'Total (?:Withdrawals|Debit|Debits)(?::)?\s*([\d,.]+)'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            total_withdrawals = match.group(1)
            return total_withdrawals
        else:
            return None

    def validate_date(self, date_text):
        try:
            if date_text != datetime.strptime(date_text, "%Y-%m-%d").strftime('%Y-%m-%d'):
                raise ValueError
            return True
        except ValueError:
            return False

    def get_average_monthly_balance(self, dataframe):
        return dataframe.groupby(
            [dataframe['Transaction Date'].dt.year.rename('Year'),
             dataframe['Transaction Date'].dt.month.rename('Month')], as_index=False
        )['Balance'].mean()

    def categorize_salary(self, dataframe, column_to_categorize):
        # salary_keywords = ['nft']
        salary_keywords = ['pension', 'sal', 'salary', 'fgn ippis', 'fgnipis', 'fgn sal', 'fgn salary', 'nft', 'cpc',
                           'fbn',
                           'subeb']
        dataframe['IsSalary'] = dataframe[column_to_categorize].str.lower().apply(
            lambda x: any(keyword in x for keyword in salary_keywords))
        salary_transactions = dataframe[dataframe['IsSalary']]
        return salary_transactions

    def categorize_by_credit_amount(self, dataframe, lower_bound, upper_bound, column_to_categorize):

        # Filter the DataFrame to get rows with 'Credit' values within the specified range
        filtered_df = dataframe[
            (dataframe[column_to_categorize] >= lower_bound) & (dataframe[column_to_categorize] <= upper_bound)]

        # Get the unique 'Credit' values within the specified range
        unique_credit_values = filtered_df[column_to_categorize].unique()

        # Find occurrences of each unique credit amount within the range and store in a dictionary
        occurrence_count_dict = {amount: filtered_df[column_to_categorize].eq(amount).sum() for amount in
                                 unique_credit_values}

        # Print the occurrence count of each unique credit amount within the range
        for amount, occurrence_count in occurrence_count_dict.items():
            print(
                f"The occurrence count of {amount} within the range {lower_bound} to {upper_bound} is: {occurrence_count}")

    def format_dataframe_columns(self, table_headers, table_rows):
        if len(table_headers) > 0 and len(table_rows) > 0:
            df = pd.DataFrame(table_rows, columns=table_headers)
            if 'Debits' in table_headers:
                self.rename_column(df, 'Debits', self.WITHDRAWAL_COLUMN_NAME)
            elif 'Debit' in table_headers:
                self.rename_column(df, 'Debit', self.WITHDRAWAL_COLUMN_NAME)
            elif 'Pay Out' in table_headers:
                self.rename_column(df, 'Pay Out', self.WITHDRAWAL_COLUMN_NAME)

            if 'Credits' in table_headers:
                self.rename_column(df, 'Credits', self.DEPOSIT_COLUMN_NAME)
            elif 'Credit' in table_headers:
                self.rename_column(df, 'Credit', self.DEPOSIT_COLUMN_NAME)
            elif 'Lodgements' in table_headers:
                self.rename_column(df, 'Lodgements', self.DEPOSIT_COLUMN_NAME)
            elif 'Pay In' in table_headers:
                self.rename_column(df, 'Pay In', self.DEPOSIT_COLUMN_NAME)

            ## rename date columns
            if 'Date' in table_headers:
                self.rename_column(df, 'Date', self.TRANSACTION_DATE_NAME)
            elif 'Trans Date' in table_headers:
                self.rename_column(df, 'Trans Date', self.TRANSACTION_DATE_NAME)
            elif 'Date Posted' in table_headers:
                self.rename_column(df, 'Date Posted', self.TRANSACTION_DATE_NAME)
            elif 'TransDate' in table_headers:
                self.rename_column(df, 'TransDate', self.TRANSACTION_DATE_NAME)
            elif 'Txn Date' in table_headers:
                self.rename_column(df, 'Txn Date', self.TRANSACTION_DATE_NAME)

            if 'ValueDate' in table_headers:
                self.rename_column(df, 'ValueDate', self.VALUE_DATE_COLUMN_NAME)
            elif 'Val Date' in table_headers:
                self.rename_column(df, 'Val Date', self.VALUE_DATE_COLUMN_NAME)

            if 'Remarks' in table_headers:
                self.rename_column(df, 'Remarks', self.DESCRIPTION_COLUMN_NAME)
            elif 'Narration' in table_headers:
                self.rename_column(df, 'Narration', self.DESCRIPTION_COLUMN_NAME)
            elif 'Transaction Details' in table_headers:
                self.rename_column(df, 'Transaction Details', self.DESCRIPTION_COLUMN_NAME)
            elif 'Details' in table_headers:
                self.rename_column(df, 'Details', self.DESCRIPTION_COLUMN_NAME)

            df['Transaction Date'] = df['Transaction Date'].apply(self.try_multiple_date_formats)
            df['Value Date'] = df['Value Date'].apply(self.try_multiple_date_formats)
            # df['Value Date'] = df['Value Date'].apply(bank_statement.clean_date_v2, format='%d-%b-%Y')
            df['Withdrawals'] = self.clean_money('Withdrawals', df)
            df['Balance'] = self.clean_money('Balance', df)
            df['Deposits'] = self.clean_money('Deposits', df)
            df['Description'] = self.clean_column(df, 'Description')

            # Replace NaT values with a custom string, e.g., 'Not Available'

            df['Value Date'] = df['Value Date'].fillna('Invalid Date')
            df['Transaction Date'] = df['Transaction Date'].fillna('Invalid Date')
            df['Withdrawals'] = df['Withdrawals'].fillna(0)
            df['Deposits'] = df['Deposits'].fillna(0)
            df['Balance'] = df['Balance'].fillna(0)

            return df

    @abstractmethod
    def predict_salary_income(self, dataframe, table_headers, lower_bound, upper_bound):
        pass

    def is_unique_amount_in_month_year(self, row, bank_df):
        amount = row['Deposits']
        month_year = (row['Transaction Date'].year, row['Transaction Date'].month)
        return len(bank_df[(bank_df['Deposits'] == amount) & (bank_df['Transaction Date'].dt.year == month_year[0]) & (
                bank_df['Transaction Date'].dt.month == month_year[1])]) == 1

    @abstractmethod
    def result(self):
        pass

    def get_average_monthly_balance(self, dataframe):
        dataframe['Transaction date'] = pd.to_datetime(dataframe['Transaction Date'])
        dataframe['Balance'] = pd.to_numeric(dataframe['Balance'])
        dataframe['YearMonth'] = dataframe['Transaction Date'].dt.to_period('M')
        monthly_average_balance = dataframe.groupby('YearMonth')['Balance'].mean()
        return monthly_average_balance.mean()
