<?php 
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
$categ=null;
if (isset($_REQUEST['idCategory'])) {
  $categ=$_REQUEST['idCategory'];
}
$lstIdOfSubCateg=null;
if(RequestHandler::isCodeSet('lstRepId')){
  $lstIdOfSubCateg=RequestHandler::getValue('lstRepId');
  $referTo=(RequestHandler::isCodeSet('referTo')?RequestHandler::getValue('referTo'):'');
  if(pq_strpos($lstIdOfSubCateg,',')==false){
    $rep= new Report($lstIdOfSubCateg);
    $repCat= new ReportCategory($lstIdOfSubCateg);
    $whereCat="idReportCategory=".Sql::fmtId($lstIdOfSubCateg);
    $lstSubCateg=$rep->getSqlElementsFromCriteria(null,false,$whereCat);
    foreach ($lstSubCateg as $tmp) {
      if ($lstIdOfSubCateg) $lstIdOfSubCateg.=',';
      $lstIdOfSubCateg.=$tmp->id;
    }
    $namSubCateg=$repCat->name;
  }else{
    $namSubCateg=(RequestHandler::isCodeSet('nameSubCat'))?RequestHandler::getValue('nameSubCat'):$referTo;
  }
}

if (RequestHandler::isCodeSet('repId')) {
  $repId = RequestHandler::getValue('repId');
  $rep = new Report($repId);
  $categ  = $rep->idReportCategory;
  $repCat = new ReportCategory($categ );
  $namSubCateg=$repCat->name;

  if (RequestHandler::isCodeSet('lstSubCat')) {
    $lstIdOfSubCateg = RequestHandler::getValue('lstSubCat');
  }
  
  if (RequestHandler::isCodeSet('namSubCateg')) {
    $namSubCateg = RequestHandler::getValue('namSubCateg');
  }
}

$hr=new HabilitationReport();
$user=getSessionUser();
$allowedReport=array();
$allowedCategory=array();
$lst=$hr->getSqlElementsFromCriteria(array('idProfile'=>$user->idProfile, 'allowAccess'=>'1'), false);
foreach ($lst as $h) {
  $report=$h->idReport;
  $reportFile = SqlList::getFieldFromId('Report', $report, 'file');
  if(pq_strpos($reportFile, 'reportLayoutId') != ''){
    $reportLayoutId = pq_substr($reportFile, (pq_strpos($reportFile, 'reportLayoutId')+15));
    $isShared = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'isShared');
    $idUser = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'idUser');
    if($isShared == '0' and $idUser != getSessionUser()->id)continue;
  }
  $nameReport=SqlList::getNameFromId('Report', $report, false);
  if (! Module::isReportActive($nameReport)) continue;
  $allowedReport[$report]=$report;
  $category=SqlList::getFieldFromId('Report', $report, 'idReportCategory',false);
  $allowedCategory[$category]=$category;
}

if (!$categ) {
  echo "<div class='messageData headerReport' style= 'white-space:nowrap;margin-top:5px'>";
  echo pq_ucfirst(i18n('colCategory'));
  echo "</div>";
  $listCateg=SqlList::getList('ReportCategory');
  echo "<ul class='bmenu'>";
  foreach ($listCateg as $id=>$name) {
    if (isset($allowedCategory[$id])) {
      echo "<li class='sectionCategorie' onClick='loadDiv(\"../view/reportListMenu.php?idCategory=$id\",\"reportMenuList\");'><div class='bmenuCategText'>$name</div></li>";
    }
  }
  echo "</ul>";
} else {
  $catObj=new ReportCategory($categ);
  $title=i18n($catObj->name);
  if($lstIdOfSubCateg){
    //$title=i18n(pq_ucfirst($namSubCateg));
    $title=i18n($namSubCateg);
    if (pq_substr($title,0,1)=='[') $title=i18n(pq_ucfirst($namSubCateg));
    if($title == "[]")$title=i18n($catObj->name);
  }
  if($title=="[../tool/jsonPlanning]")$title=i18n('GanttPlan');
  echo "<div class='messageData headerReport' style= 'white-space:nowrap;margin-top:5px'>";
  echo $title;
  echo "</div>";
  echo "<div class='arrowBack' style='position:absolute;top:5px;left:25px;'>";
  if($lstIdOfSubCateg)$undo="loadDiv(\"../view/reportListMenu.php?idCategory=$categ\",\"reportMenuList\")";
  else $undo="loadDiv(\"../view/reportListMenu.php\",\"reportMenuList\")";
  echo "<span class='dijitInline dijitButtonNode backButton noRotate'  onClick='$undo' style='border:unset;'>";
  if(isNewGui()){
    echo formatNewGuiButton('Back', 22);
  }else{
    echo formatBigButton('Back'); 
  }
  echo "</div>";
  echo '</span>';
  
  if (isset($rep) and $rep !== null) {
    $report = $rep;
  } else {
    $report=new Report();
  }
  $res=array();
  
  
  //================================Sort reports and category ==============================================//
  $lstReportName=array();
  $lstNewListReport=array();
  
  if(!$lstIdOfSubCateg){
    $crit=array('idReportCategory'=>$categ);
    $listReport=$report->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
    $nameOfFiles=SqlList::getListWithCrit("Report","idReportCategory = $categ and (referTo IS NULL or referTo='') and id not in (21,22)","file");
    $referToList=SqlList::getListWithCrit("Report","idReportCategory = $categ and referTo IS NOT NULL and referTo<>''","referTo");
    
    foreach ($nameOfFiles as $idN=>$nameFile){
      $lstReportName[]=pq_substr($nameFile, 0,pq_strpos($nameFile, '.php'));
    }
    $countNameFil=array_count_values($lstReportName);
    foreach ($countNameFil as $name=>$val){
      if($val==1)unset($countNameFil[$name]);
      else $lstNewListReport[]=$name;
    }
    
    if(!empty($referToList))$lstNewListReport=array_unique(array_merge($lstNewListReport,array_unique($referToList)));
    storReportsView($listReport, $res, $lstNewListReport);
  }else{
    $where="idReportCategory=$categ and id in ($lstIdOfSubCateg)";
    $listReport=$report->getSqlElementsFromCriteria(null, false, $where, 'sortOrder asc');
  }

  ksort($res);
 //==================================================================================//
 
  echo "<ul class='bmenu report' style=''>";
  if(!empty($res)){
    foreach ($res as $rpt) {
      $id=$rpt['object']['id'];
      $name=$rpt['object']['name'];
      $isReportList = (isset($rpt['reportLayoutId']))?true:false;
      $reportLayout = null;
      if($rpt['objectType']=='reportSubMenu'){
        $lstRepId=$rpt['object']['lstRepId'];
        $referToVal=$rpt['object']['referTo'];
        if($name=='../tool/jsonPlanning')$name='GanttPlan';
        $valueToSend = 'repId=' . $id;
        echo "<li class='sectionCategorie' onClick='loadDiv(\"../view/reportListMenu.php?idCategory=$categ&lstRepId=$lstRepId&referTo=$referToVal&nameSubCat=$name\",\"reportMenuList\");'><div class='bmenuCategText'>".i18n($name)."</div></li>";
      }else{
        if (isset($allowedReport[$id])) {
          $valueToSend = 'repId=' . $id;
          if (isset($repId) and $repId == $id) {
            $class = 'reportSelected';
          } else {
            $class = '';
          }
          $reportName = pq_ucfirst(i18n($name));
          echo "<li class='section $class' id='report$id' onClick='reportSelectReport($id);stockHistory(\"Reports\",\"$valueToSend\", \"Reports\");'><div class='bmenuText'>".$reportName."</div></li>";
        }
      }
    }
  }else{
    foreach ($listReport as $rpt) {
      if (isset($repId) and $repId == $rpt->id) {
        $class = 'reportSelected';
      } else {
        $class = '';
      }
      $isReportList=false;
      $reportLayoutName = '';
      $isShared = '0';
      $idUser = null;
      if (isset($allowedReport[$rpt->id])) {
        if(pq_strpos($rpt->file, 'reportLayoutId')){
          $isReportList = true;
          $reportLayoutId = pq_substr($rpt->file, (pq_strpos($rpt->file, 'reportLayoutId')+15));
          $reportName = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'scope');
          $isShared = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'isShared');
          $idUser = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'idUser');
          if($isShared == '0' and $idUser != getSessionUser()->id)continue;
        }else{
          $isReportList=false;
        }
        if(!$isReportList)$reportName = pq_ucfirst(i18n($rpt->name));
        $valueToSend = 'repId='.$rpt->id.'&lstSubCat='.$lstIdOfSubCateg.'&namSubCateg='.$namSubCateg;
        echo "<li class='section $class' id='report$rpt->id' onClick='reportSelectReport($rpt->id);stockHistory(\"Reports\",\"$valueToSend\", \"Reports\");'>";
        if($isShared == '1' and $idUser != getSessionUser()->id){
          $sharedUserName = SqlList::getNameFromId('Affectable', $idUser, false);
          echo "<div style='float:left;position: absolute;top: 16px;padding-left: 15px;'><img src='css/images/share.png' title='".i18n('sharedBy', array($sharedUserName))."'/></div>";
        }
        echo "<div class='bmenuText'>".$reportName."</div></li>";
      }
    }
  }
  echo "</ul>";
}



function storReportsView($listReport, &$res, $lstNewListReport ) { //store report
  $count=array();
  $isNewPId=array();
  foreach ($listReport as $id=>$report){
    if($report->id=="108" and !Module::isModuleActive('moduleTechnicalProgress'))continue;
    $referTo=false;
    
    if($report->referTo!=''){
      $file=$report->referTo;
      $referTo=true;
    }else{
      $file=pq_substr($report->file, 0,pq_strpos($report->file, '.php'));
    }

    $menuName = 'menu'.$file;
    $menuId = SqlList::getIdFromTranslatableName('Menu', $menuName);
    if($menuId != ""){
      if(!securityCheckDisplayMenu($menuId,$file))continue;
    }
    
    if(in_array($file, $lstNewListReport)){
      if(!isset($count[$file])){
        if(pq_strpos($report->file, 'reportLayoutId') != ''){
          $reportLayoutId = pq_substr($report->file, (pq_strpos($report->file, 'reportLayoutId')+15));
          $isShared = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'isShared');
          $idUser = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'idUser');
          if($isShared == '0' and $idUser != getSessionUser()->id)continue;
        }
        $sortOrder=$report->sortOrder;
        $count[$file]=1;
        $keyParent=numericFixLengthFormatter($sortOrder,10);
        $isNewPId[$file]=$sortOrder;
        $obj= array('id'=>$isNewPId[$file],'name'=>pq_ucfirst($file),'lstRepId'=>$report->id,'referTo'=>(($referTo)?$file:''));
        $res[$keyParent]=array('objectType'=>'reportSubMenu','object'=>$obj);
      }else{
        $key=numericFixLengthFormatter($isNewPId[$file],10);
        $res[$key]['object']['lstRepId'].=','.$report->id;
      }
    }else{
      $keyParent=numericFixLengthFormatter(('100'.$report->sortOrder),10);
      $obj= array('id'=>$report->id,'name'=>$report->name);
      if(pq_strpos($report->file, 'reportLayoutId') != ''){
        $reportLayoutId = pq_substr($report->file, (pq_strpos($report->file, 'reportLayoutId')+15));
        $isShared = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'isShared');
        $idUser = SqlList::getFieldFromId('ReportLayout', $reportLayoutId, 'idUser');
        if($isShared == '0' and $idUser != getSessionUser()->id)continue;
      }
      $res[$keyParent]=array('objectType'=>'reportDirect','object'=>$obj);
      if(pq_strpos($report->file, 'reportLayoutId')){
        $reportLayoutId = pq_substr($report->file, (pq_strpos($report->file, 'reportLayoutId')+15));
        $res[$keyParent]['reportLayoutId'] = $reportLayoutId;
      }
    }
  }
}
?>