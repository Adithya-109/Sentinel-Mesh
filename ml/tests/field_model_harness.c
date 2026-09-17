/* Test harness for the field-model C export: reads a headerless CSV of
 * FEATURE_ORDER-ordered float rows (see sentinel_ml/field_model.py) from
 * argv[1], calls classify_window() on each, and prints one predicted
 * class index per line. Compared against sklearn's predict() in Python
 * by test_field_model_pipeline.py -- this file itself never changes
 * between runs, only synthetic_field_model.h (regenerated per run) does.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "synthetic_field_model.h"

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
        printf("%d\n", classify_window(f));
    }

    fclose(fp);
    return 0;
}
