"""Create local demo database AiBiDemo with dbo.SalesView for this prototype."""
import pyodbc

SERVER = r'(localdb)\MSSQLLocalDB'
DRIVER = 'ODBC Driver 17 for SQL Server'
DB = 'AiBiDemo'


def connect(database='master'):
    return pyodbc.connect(
        f'DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={database};'
        f'Trusted_Connection=yes;Connection Timeout=10',
        autocommit=True,
        timeout=10,
    )


def main():
    with connect('master') as conn:
        cur = conn.cursor()
        exists = cur.execute(
            "SELECT 1 FROM sys.databases WHERE name = ?", DB
        ).fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE [{DB}]')
            print(f'Created database {DB}')
        else:
            print(f'Database {DB} already exists')

    with connect(DB) as conn:
        cur = conn.cursor()
        cur.execute('''
IF OBJECT_ID(N'dbo.SalesRaw', N'U') IS NULL
BEGIN
  CREATE TABLE dbo.SalesRaw (
    SaleId int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    SaleDate date NOT NULL,
    Amount decimal(18,2) NOT NULL,
    Category nvarchar(50) NOT NULL,
    Region nvarchar(50) NOT NULL
  );
END
''')
        count = cur.execute('SELECT COUNT(*) FROM dbo.SalesRaw').fetchone()[0]
        if count == 0:
            cur.execute('''
INSERT INTO dbo.SalesRaw (SaleDate, Amount, Category, Region) VALUES
(N'2025-01-05', 1200.00, N'Electronics', N'Центр'),
(N'2025-01-18', 450.50, N'Home', N'Север'),
(N'2025-02-03', 980.00, N'Electronics', N'Юг'),
(N'2025-02-14', 310.25, N'Clothing', N'Центр'),
(N'2025-03-01', 1500.00, N'Electronics', N'Север'),
(N'2025-03-22', 220.00, N'Home', N'Юг'),
(N'2025-04-09', 875.75, N'Clothing', N'Центр'),
(N'2025-04-27', 640.00, N'Electronics', N'Юг'),
(N'2025-05-11', 410.00, N'Home', N'Север'),
(N'2025-05-29', 1320.40, N'Electronics', N'Центр'),
(N'2025-06-07', 255.00, N'Clothing', N'Юг'),
(N'2025-06-19', 990.00, N'Home', N'Центр'),
(N'2025-07-02', 1100.00, N'Electronics', N'Север'),
(N'2025-07-21', 360.50, N'Clothing', N'Центр'),
(N'2025-08-08', 780.00, N'Home', N'Юг'),
(N'2025-08-25', 1450.00, N'Electronics', N'Центр'),
(N'2025-09-04', 510.25, N'Clothing', N'Север'),
(N'2025-09-16', 870.00, N'Home', N'Центр');
''')
            print('Inserted demo sales rows')
        else:
            print(f'SalesRaw already has {count} rows')

        cur.execute('''
IF OBJECT_ID(N'dbo.SalesView', N'V') IS NOT NULL
  DROP VIEW dbo.SalesView;
''')
        cur.execute('''
CREATE VIEW dbo.SalesView AS
SELECT SaleDate, Amount, Category, Region
FROM dbo.SalesRaw;
''')
        cur.execute('''
IF EXISTS (
  SELECT 1 FROM sys.extended_properties
  WHERE major_id = OBJECT_ID(N'dbo.SalesView') AND minor_id = 0 AND name = N'MS_Description'
)
  EXEC sys.sp_dropextendedproperty
    @name = N'MS_Description', @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'VIEW', @level1name = N'SalesView';
EXEC sys.sp_addextendedproperty
  @name = N'MS_Description',
  @value = N'Продажи по дате, сумме, категории и региону',
  @level0type = N'SCHEMA', @level0name = N'dbo',
  @level1type = N'VIEW', @level1name = N'SalesView';
''')
        for col, desc in [
            ('SaleDate', 'Дата продажи'),
            ('Amount', 'Сумма продажи в валюте отчёта'),
            ('Category', 'Категория товара'),
            ('Region', 'Регион продаж'),
        ]:
            cur.execute(f'''
IF EXISTS (
  SELECT 1 FROM sys.extended_properties ep
  JOIN sys.columns c ON c.object_id = ep.major_id AND c.column_id = ep.minor_id
  WHERE ep.major_id = OBJECT_ID(N'dbo.SalesView') AND c.name = N'{col}' AND ep.name = N'MS_Description'
)
  EXEC sys.sp_dropextendedproperty
    @name = N'MS_Description', @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'VIEW', @level1name = N'SalesView',
    @level2type = N'COLUMN', @level2name = N'{col}';
EXEC sys.sp_addextendedproperty
  @name = N'MS_Description', @value = N'{desc}',
  @level0type = N'SCHEMA', @level0name = N'dbo',
  @level1type = N'VIEW', @level1name = N'SalesView',
  @level2type = N'COLUMN', @level2name = N'{col}';
''')
        rows = cur.execute('SELECT COUNT(*) FROM dbo.SalesView').fetchone()[0]
        print(f'Ready: dbo.SalesView with {rows} rows')


if __name__ == '__main__':
    main()
