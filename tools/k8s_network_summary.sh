#!/bin/bash

NAMESPACE="smartem-decisions"

echo "=== KUBERNETES NETWORK SUMMARY ==="
echo

echo "1. PODS AND THEIR IPs:"
kubectl get pods -n $NAMESPACE -o wide

echo -e "\n2. SERVICES AND PORT MAPPINGS:"
kubectl get services -n $NAMESPACE -o wide

echo -e "\n3. NODE PORTS (External Access):"
kubectl get services -n $NAMESPACE --field-selector spec.type=NodePort -o custom-columns="NAME:.metadata.name,TYPE:.spec.type,CLUSTER-IP:.spec.clusterIP,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip,PORT(S):.spec.ports[*].port,NODEPORT:.spec.ports[*].nodePort"

echo -e "\n4. DETAILED PORT MAPPINGS:"
echo "Service -> Pod mappings:"
for svc in $(kubectl get services -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}'); do
    echo "--- $svc ---"
    kubectl describe service $svc -n $NAMESPACE | grep -E "(Port:|TargetPort:|NodePort:|Endpoints:)"
done

echo -e "\n5. ENDPOINTS (Service -> Pod connections):"
kubectl get endpoints -n $NAMESPACE

echo -e "\n6. INGRESS/LOAD BALANCERS:"
kubectl get ingress -n $NAMESPACE 2>/dev/null || echo "No ingress found"

echo -e "\n7. CONTAINER PORTS IN PODS:"
for pod in $(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}'); do
    echo "--- $pod ---"
    kubectl get pod $pod -n $NAMESPACE -o jsonpath='{.spec.containers[*].ports[*]}{"\n"}' | grep -v '^$' || echo "No ports defined"
done

echo -e "\n8. QUICK ACCESS SUMMARY:"
echo "External access points (NodePort services):"
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
kubectl get services -n $NAMESPACE --field-selector spec.type=NodePort -o custom-columns="SERVICE:.metadata.name,ACCESS:.spec.ports[*].nodePort" --no-headers | while read service nodeport; do
    echo "  $service: http://$NODE_IP:$nodeport"
done

echo -e "\n9. NETWORK POLICIES:"
kubectl get networkpolicies -n $NAMESPACE 2>/dev/null || echo "No network policies found"
