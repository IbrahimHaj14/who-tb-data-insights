from src.data_cleaning.extract_raw import TBDataExtractor

if __name__ == "__main__":
    loader = TBDataExtractor("tb_outcomes.csv")  
    df = loader.load()

    print(df.tail(70))
    print(f"\nLoaded {len(df)} rows.")
