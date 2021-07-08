Ansible logo from https://www.ansible.com/logos

Build gif from mkv with:
```
.\ffmpeg --% -i "input.mkv" -filter_complex "[0:v] \
fps=12,scale=680:-1,split [a][b];[a] palettegen [p];[b][p] paletteuse" \
"output.gif"
```
