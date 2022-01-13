#!/usr/bin/python3
import subprocess


def connect_all():
    ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
    port_list = []
    client = "0"
    for line in str(ports).splitlines():
        if line.startswith("client "):
            client = line[7:].split(":", 2)[0]
            if client == "0" or "Through" in line:
                client = "0"
        else:
            if client == "0" or line.startswith('\t'):
                continue
            port = line.split()[0]
            port_list.append(client + ":" + port)
    for source in port_list:
        for target in port_list:
            if source != target:
                # print("aconnect %s %s" % (source, target))
                subprocess.call("aconnect %s %s" % (source, target), shell=True)


if __name__ == '__main__':
    connect_all()
