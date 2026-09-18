/* Test harness for the EnergyGate C export: reads a headerless CSV of
 * FEATURE_ORDER-ordered float rows (see sentinel_ml/energygate.py) from
 * argv[1], calls energygate_score() on each, and prints one predicted
 * probability per line. Compared against sklearn's predict_proba() in
 * Python by test_energygate_pipeline.py -- this file itself never changes
 * between runs, only synthetic_energygate.h (regenerated per run) does.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "synthetic_energygate.h"

#define MAX_FEATURES 32
#define LINE_LEN 2048

int main(int argc, char** argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <features.csv>\n", argv[0]);
        return 2;
    }
    FILE* fp = fopen(argv[1], "r");
    if (!fp) {
        fprintf(stderr, "could not open %s\n", argv[1]);
        return 2;
    }

    char line[LINE_LEN];
    while (fgets(line, sizeof(line), fp)) {
        float f[MAX_FEATURES];
        int n = 0;
        char* tok = strtok(line, ",\n");
        while (tok && n < MAX_FEATURES) {
            f[n++] = (float)atof(tok);
            tok = strtok(NULL, ",\n");
        }
        if (n == 0) continue;
        printf("%.6f\n", energygate_score(f));
    }

    fclose(fp);
    return 0;
}
