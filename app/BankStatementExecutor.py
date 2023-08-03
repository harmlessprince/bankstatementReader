import subprocess


class BankStatementExecutor:
    def __init__(self):
        self.bank_statements = {
            1: "Zenith",
            2: "UBA",
            3: "Access",
            4: "First",
            5: "GT",
            6: "FCMB",
            7: "Fidelity",
            8: "Sterling"
            # Add more bank statements with corresponding numbers here
        }

    def close(self):
        exit(0)
    def display_menu(self):
        print("Available Bank Statements:")
        for number, statement in self.bank_statements.items():
            print(f"{number}. {statement}")

    def get_user_choice(self):
        while True:
            try:
                choice = int(input("Select a number to execute the corresponding bank statement: "))
                if choice in self.bank_statements:
                    return choice
                else:
                    print("Invalid option. Please choose a valid number.")
            except ValueError:
                self.display_menu()
                print("Invalid input. Please enter a number.")

    def execute_bank_statement(self, choice):
        file_to_execute = self.bank_statements.get(choice)
        print(file_to_execute + " Bank Statement Selected")
        file_to_execute = file_to_execute + "BankStatement.py"
        if file_to_execute:
            try:
                subprocess.run(["python", file_to_execute], check=True)
            except subprocess.SubprocessError:
                print(f"Error executing {file_to_execute}.")
            except FileNotFoundError:
                print(f"Error: {file_to_execute} not found.")
            except Exception as e:
                print(f"Error executing {file_to_execute}: {e}")
        else:
            print("Invalid option. Unable to execute the selected bank statement.")


if __name__ == "__main__":
    executor = BankStatementExecutor()
    executor.display_menu()
    choice = executor.get_user_choice()
    executor.execute_bank_statement(choice)
