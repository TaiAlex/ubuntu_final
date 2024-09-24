#!/bin/bash
nohup python3 ./server/api.py &
nohup python3 ./server/microSev.py &
nohup sudo systemctl start mongod &
