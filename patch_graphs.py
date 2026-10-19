import re
p = "experiments/make_graphs.py"
s = open(p).read()

# short scenario names for readable x-axis labels
s = s.replace('COLOR = {"A": "#999999", "B": "#e69f00", "C": "#0072b2"}\n',
 'COLOR = {"A": "#999999", "B": "#e69f00", "C": "#0072b2"}\n'
 'SHORT = {"S1": "Legit\\nkeyboard", "S2": "Unknown\\nfast", "S3": "Spoofed\\nfast, plain", "S4": "Spoofed\\nfast, shell",\n'
 '         "S5": "Composite\\n(simulated)", "S6": "Fast human\\ntypist", "S7": "Spoofed\\nslow, plain",\n'
 '         "S8": "Spoofed\\nslow, shell", "S9": "Barcode\\nscanner", "S10": "Identical\\nkeyboard"}\n\n\n'
 'def tick(s):\n    return f"{s}\\n{SHORT.get(s, \'\')}"\n', 1)

# grouped(): readable labels, legend above the bars
s = s.replace('    ax.set_xticks(x)\n    ax.set_xticklabels(scens)\n    ax.set_ylabel(ylabel)\n    ax.legend(fontsize=8)',
              '    ax.set_xticks(x)\n    ax.set_xticklabels([tick(sc) for sc in scens], fontsize=8)\n    ax.set_ylabel(ylabel)\n    ax.legend(fontsize=8, loc="upper center", ncol=3)', 1)

# figure 1
s = s.replace('    ax.set_ylim(0, 115)\n    ax.set_title("Attack detection rate by system and scenario")',
              '    ax.set_ylim(0, 128)\n    ax.set_title("Attack detection rate by system and scenario")', 1)
s = re.sub(r'    ax\.set_xlabel\("Scenario \(.*\n', '    ax.set_xlabel("Attack scenario")\n', s, count=1)
# figure 2
s = s.replace("        a.set_ylim(0, 115)", "        a.set_ylim(0, 128)", 1)
# figure 3
s = s.replace('grouped(ax, attack, lambda d: d["leaked"].mean(), "Mean keystrokes that reached the system")',
              'grouped(ax, attack, lambda d: d["leaked"].mean(), "Mean keystrokes that reached the system")\n    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)', 1)
# figure 4
s = s.replace('    ax.set_xticklabels(scens)\n    ax.set_ylabel("Mean time',
              '    ax.set_xticklabels([tick(sc) for sc in scens], fontsize=8)\n    ax.set_ylabel("Mean time', 1)
open(p, "w").write(s)
print("patched")
