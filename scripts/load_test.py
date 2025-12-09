from src.data_cleaning.load_raw import TBDataLoader

if __name__ == "__main__":
    loader = TBDataLoader("tb_outcomes.csv")  
    df = loader.load()

    print(df.tail(70))
    print(f"\nLoaded {len(df)} rows.")
