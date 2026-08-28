#!/bin/bash

for file in Test*.tex
do
    echo "Prevajam $file"
    pdflatex "$file"
done
``
