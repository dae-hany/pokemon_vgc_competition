import os
from collections import defaultdict

import matplotlib.pyplot as plt


class RuleObserver:
    def __init__(self):
        self.rule_counts = defaultdict(int)

    def track_success(self, rule_name):
        self.rule_counts[rule_name] += 1

    def plot(self, name):
        if not self.rule_counts:
            print("Keine aktiven Regelverwendungen zum Plotten.")
            return

        # Sortiere absteigend (größter zuerst), dann kehre um für barh
        sorted_items = sorted(self.rule_counts.items(), key=lambda item: item[1])
        keys = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]

        plt.figure(figsize=(12, 6))
        bars = plt.barh(keys, values, color="#0088FF")
        plt.ylabel("Rule Name")
        plt.xlabel("Triggered Count")
        plt.title("Anzahl erfolgreicher Regel-Anwendungen")
        plt.tight_layout()
        plt.grid(axis='x', linestyle='--', alpha=0.7)

        for bar in bars:
            width = bar.get_width()
            plt.text(width, bar.get_y() + bar.get_height() / 2, int(width), va='center', ha='left', fontsize=10,
                     color='black')

        os.makedirs(f"models/{name}/plots", exist_ok=True)
        plt.savefig(f"models/{name}/plots/rule_usage.pdf")
        plt.show()
        plt.close()
