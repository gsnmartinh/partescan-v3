import multiprocessing
from parte_scan.servidor import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
