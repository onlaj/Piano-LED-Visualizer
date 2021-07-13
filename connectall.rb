#!/usr/bin/ruby

t = `aconnect -i -l`
$devices = {}
$device = 0
t.lines.each do |l|
  match = /client (\d*)\:((?:(?!client).)*)?/.match(l)
  # we skip empty lines and the "Through" port
  unless match.nil? || match[1] == '0' || /Through/=~l
    $device = match[1]
    $devices[$device] = []
  end
  match = /^\s+(\d+)\s/.match(l)
  if !match.nil? && !$devices[$device].nil?
    $devices[$device] << match[1]
  end
end

$devices.each do |device1, ports1|
  ports1.each do |port1|
    $devices.each do |device2, ports2|
      ports2.each do |port2|
        # probably not a good idea to connect a port to itself
        unless device1 == device2 && port1 == port2
          system "aconnect #{device1}:#{port1} #{device2}:#{port2}"
        end
      end
    end
  end
end