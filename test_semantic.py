import main
import datetime

print(f"[{datetime.datetime.now()}] Calling load_data()...", flush=True)
main.load_data()
print(f"[{datetime.datetime.now()}] load_data() completed.", flush=True)

symptom = "nóng lạnh, đau đầu, buồn nôn, khô môi, ho có đờm xanh"
print(f"[{datetime.datetime.now()}] Testing inference with: {symptom}", flush=True)
res = main.expert_system_inference(symptom)
print("Result:")
for r in res:
    print(r)
