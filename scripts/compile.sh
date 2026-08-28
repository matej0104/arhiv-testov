#!/bin/bash

for file in Test*.tex
do
    echo "Prevajam $file"

    pdflatex -interaction=nonstopmode "$file"
    pdflatex -interaction=nonstopmode "$file"

done
