<?php
require_once "../tool/projeqtor.php";
$operation=RequestHandler::getValue('operation',true);
$pool=RequestHandler::getValue('pool',true);
$capa=RequestHandler::getValue('capa',($operation=='extra')?true:false);

$result="OK";
$message="No error for operation=$operation, pool=$pool";
$altered='?';

//$pool=new ResourceTeam($pool);
$crit=array('idResource'=>$pool,'idUser'=>getCurrentUserId(),'idScenario'=>null);
$crsp=SqlElement::getSingleSqlElementFromCriteria('CriticalResourceScenarioPool', $crit);

if ($operation=='extra') {
  if ($capa) {
    $altered='YES';
    $crsp->extracapacity=$capa;
    $resSave=$crsp->save();
  } else  if ($crsp->id) {
    $altered='NO';
    $resSave=$crsp->delete();
    $result="DEL";
  }
  if($result!="DEL")$result=getLastOperationStatus($resSave);
  if ($result!='OK') $message=strip_tags($resSave);
  echo '{"result":"'.$result.'","message":"'.$message.'", "altered":"'.$altered.'"}';
} else {
  echo '{"result":"ERROR","message":"unexpected operation \''.$operation.'\'", "newstatus":"", "altered":""}';
}
