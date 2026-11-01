<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Presents an object.
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/documentExplorerMain.php');

  $currentScreen='DocumentExplorer';
  $notGlobal=RequestHandler::getBoolean('notGlobal');
  $paramScreen='';
  if(RequestHandler::isCodeSet('paramScreen_'.$currentScreen)){
    $paramScreen=RequestHandler::getValue('paramScreen_'.$currentScreen);
  }else if(RequestHandler::isCodeSet('paramScreen')){
    $paramScreen=RequestHandler::getValue('paramScreen');
  }
  $paramLayoutObjectDetail=RequestHandler::getValue('paramLayoutObjectDetail');
  if(RequestHandler::isCodeSet('paramRightDiv_'.$currentScreen)){
    $paramRightDiv=RequestHandler::getValue('paramRightDiv_'.$currentScreen);
  }else{
    $paramRightDiv=RequestHandler::getValue('paramRightDiv');
  }
  if((!$notGlobal and $paramScreen!='')){
    if($paramScreen=='top')$paramRightDiv='trailing';
    else $paramRightDiv='bottom';
  }
  setSessionValue('currentScreen', $currentScreen);
  unsetSessionValue('Directory');

  $positionListDiv=changeLayoutObjectDetail($paramScreen,$paramLayoutObjectDetail,'paramScreen_'.$currentScreen,$notGlobal);
  $positonRightDiv=changeLayoutActivityStream($paramRightDiv,'paramRightDiv_'.$currentScreen,$notGlobal);
  if(Parameter::getUserParameter('paramScreen_'.$currentScreen)){
    $codeModeLayout=Parameter::getUserParameter('paramScreen_'.$currentScreen);
  }else{
    $codeModeLayout=Parameter::getUserParameter('paramScreen');
  }
  $listHeight='';
  if ($positionListDiv=='top'){
    $listHeight=HeightLayoutListDiv($currentScreen);
  }
  if($positonRightDiv=="bottom"){
    $rightHeightPlanning=getHeightLayoutActivityStream($currentScreen);
  }else{
  	$rightWidthPlanning=getWidthLayoutActivityStream($currentScreen);
  }
  $tableWidth=WidthDivContentDetail($positionListDiv,$currentScreen);

  if ($positionListDiv=='left'
      and Parameter::getUserParameter('coversListPlan')!='CLOSE'
      and ! intval(Parameter::getUserParameter('contentPaneDetailDivWidth'.$currentScreen))
      and ! intval(Parameter::getUserParameter('contentPaneTopDetailDivWidth'.$currentScreen))) {
    $tableWidth[0]='calc(100% - 600px)';
    $tableWidth[1]='600px';
  }
  session_write_close();
  //
?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="DocumentExplorer" />
<input type="hidden" name="planning" id="planning" value="true" />
<input type="hidden" name="detailDivWidthSize" id="detailDivWidthSize" value="<?php echo intval(Parameter::getUserParameter('contentPaneDetailDivWidth'.$currentScreen));?>"/>
<input type="hidden" name="detailDivHeightSize" id="detailDivHeightSize" value="<?php echo intval(Parameter::getUserParameter('contentPaneDetailDivHeight'.$currentScreen));?>"/>
<input type="hidden" id="projectNotStartBeforeValidatedDate" value="<?php echo (Parameter::getGlobalParameter("notStartBeforeValidatedStartDate")=='YES')?1:0;?>" />
<div id="mainDivContainer" class="container" dojoType="dijit.layout.BorderContainer">
 <!-- Draws the screen on every entry path, some injecting this shell with no
      callback. Hooked on this container : a pane of its own would need a region
      here. startup, and after that of the children, dojo/connect adding to it. -->
 <script type="dojo/connect" event="startup" args="evt">
   explorerInit();
 </script>
 <div dojoType="dijit.layout.ContentPane" region="center" splitter="true">
    <div class="container" dojoType="dijit.layout.BorderContainer" liveSplitters="false">
    <div id="listBarShow" class="dijitAccordionTitle"  onMouseover="showList('mouse')" onClick="showList('click');">
		  <div id="listBarIcon" align="center"></div>
		</div>
      <div id="listDiv" dojoType="dijit.layout.ContentPane" region="<?php echo $positionListDiv; ?>" splitter="true"
      style="<?php if($positionListDiv=='top'){echo "height:".$listHeight;}else{ echo "width:".$tableWidth[0];}?>">
        <script type="dojo/connect" event="resize" args="evt">
          if (switchedMode) return;
           var paramDiv=<?php echo json_encode($positionListDiv); ?>;
           var paramMode=<?php echo json_encode($codeModeLayout); ?>;
           if(paramDiv=="top" && paramMode!='switch' && dojo.byId("contentDetailDiv").offsetHeight!=0 && coverListAction!='CLOSE'){
              saveContentPaneResizing("contentPaneTopDetailDivHeight<?php echo $currentScreen;?>",dojo.byId("listDiv").offsetHeight, true);
            }else if(paramDiv!="top" && paramMode!='switch' && dojo.byId("contentDetailDiv").offsetWidth!=0 && coverListAction!='CLOSE'){
              saveContentPaneResizing("contentPaneTopDetailDivWidth<?php echo $currentScreen;?>", dojo.byId("listDiv").offsetWidth, true);
            }
        </script>
        <?php include 'documentExplorerList.php'?>
      </div>
      <div id="contentDetailDiv" dojoType="dijit.layout.ContentPane" region="center"   style="width:<?php echo $tableWidth[1]; ?>;">
          <script type="dojo/connect" event="resize" args="evt">
           var paramDiv=<?php echo json_encode($positionListDiv); ?>;
           var paramRightDiv=<?php echo json_encode($positonRightDiv);?>;
           var paramMode=<?php echo json_encode($codeModeLayout); ?>;
           if (!ShowDetailScreenRun){
            checkValidatedSize(paramDiv,paramRightDiv, paramMode);
           }
           if(paramDiv=="top" && paramMode!='switch' && dojo.byId("contentDetailDiv").offsetHeight!=0 && coverListAction!='CLOSE'){
              saveContentPaneResizing("contentPaneDetailDivHeight<?php echo $currentScreen;?>", dojo.byId("contentDetailDiv").offsetHeight, true);
              dojo.byId('detailDivHeightSize').value=dojo.byId("contentDetailDiv").offsetHeight;
           }else if(paramDiv!="top" && paramMode!='switch' && dojo.byId("contentDetailDiv").offsetWidth!=0 && coverListAction!='CLOSE'){
             saveContentPaneResizing("contentPaneDetailDivWidth<?php echo $currentScreen;?>", dojo.byId("contentDetailDiv").offsetWidth, true);
             dojo.byId('detailDivWidthSize').value=dojo.byId("contentDetailDiv").offsetWidth;
             refreshObjectDivAfterResize();
           }
          </script>

	  <div class="container" dojoType="dijit.layout.BorderContainer"  liveSplitters="false">
	  <div id="detailBarShow" class="dijitAccordionTitle" onClick="hideDetailScreen();"
	    <?php if (RequestHandler::isCodeSet('switchedMode') and RequestHandler::getValue('switchedMode')=='on') echo ' style="display:block;"'?>>
              <div id="detailBarIcon" align="center"></div>
           </div>
          <div id="detailDiv" dojoType="dijit.layout.ContentPane" region="center">
            <?php $noselect=true; ?>
          </div>
          <?php
            if (Module::isModuleActive('moduleActivityStream')) {
              if(property_exists('Activity', '_Note') or property_exists('Project', '_Note') or property_exists('Milestone', '_Note')){
                $showNotes=true;
                $item=new Activity();
                if ($item->isAttributeSetToField('_Note','hidden')) $showNotes=false;
                else if (in_array('_Note',$item->getExtraHiddenFields(null, null, getSessionUser()->getProfile()))) $showNotes=false;
                $item=new Project();
                if ($item->isAttributeSetToField('_Note','hidden')) $showNotes=false;
                else if (in_array('_Note',$item->getExtraHiddenFields(null, null, getSessionUser()->getProfile()))) $showNotes=false;
                $item=new Milestone();
                if ($item->isAttributeSetToField('_Note','hidden')) $showNotes=false;
                else if (in_array('_Note',$item->getExtraHiddenFields(null, null, getSessionUser()->getProfile()))) $showNotes=false;
              }
            } else {
              $showNotes=false;
            }
          if ($showNotes) {?>
          <div id="detailRightDiv" dojoType="dijit.layout.ContentPane" region="<?php echo $positonRightDiv; ?>" splitter="true"
          style="<?php if($positonRightDiv=="bottom"){echo "height:".$rightHeightPlanning;}else{ echo "width:".$rightWidthPlanning;}?>" >
              <script type="dojo/connect" event="resize" args="evt">
                var paramDiv=<?php echo json_encode($positionListDiv); ?>;
                var paramRightDiv=<?php echo json_encode($positonRightDiv); ?>;
                var paramMode=<?php echo json_encode($codeModeLayout); ?>;
                hideSplitterStream (paramRightDiv);
                if (checkValidatedSizeRightDiv(paramDiv,paramRightDiv, paramMode)){
                  return;
                }
                  if(paramRightDiv=='trailing'){
                    saveContentPaneResizing("contentPaneRightDetailDivWidth<?php echo $currentScreen;?>", dojo.byId("detailRightDiv").offsetWidth, true);
                    var newWidth=dojo.byId("detailRightDiv").offsetWidth;
                    dojo.query(".activityStreamNoteContainer").forEach(function(node, index, nodelist) {
                    node.style.maxWidth=(newWidth-30)+"px";
                    });
                  }else{
                    saveContentPaneResizing("contentPaneRightDetailDivHeight<?php echo $currentScreen;?>", dojo.byId("detailRightDiv").offsetHeight, true);
                    var newHeight=dojo.byId("detailRightDiv").offsetHeight;
                    if (dojo.byId("noteNoteStream")) dojo.byId("noteNoteStream").style.height=(newHeight-40)+'px';
                  }
              </script>
              <script type="dojo/connect" event="onLoad" args="evt">
                scrollInto();
	         </script>
              <?php
              if (isset($objectClass) and $objectClass) include 'objectStream.php';
              ?>
          </div>
          <?php }?>
        </div>
      </div>
 </div>
</div> 