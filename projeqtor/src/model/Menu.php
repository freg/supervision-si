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

/*
 * ============================================================================
 * Menu defines list of items to present to users.
 */
require_once ('_securityCheck.php');

class Menu extends SqlElement {

  // extends SqlElement, so has $id
  public $id;

  // redefine $id to specify its visible place
  public $name;

  public $idMenu;

  public $type;

  public $level;

  public $sortOrder=0;

  public $menuClass;

  public $idle;

  public $isAdminMenu;

  public $_isNameTranslatable=true;

  public $_noHistory=true;

  // Will never save history for this object

  /**
   * ==========================================================================
   * Constructor
   *
   * @param $id Int
   *          the id of the object in the database (null if not stored yet)
   * @return void
   */
  function __construct($id=NULL, $withoutDependentObjects=false) {
    parent::__construct($id, $withoutDependentObjects);
  }

  /**
   * ==========================================================================
   * Destructor
   *
   * @return void
   */
  function __destruct() {
    parent::__destruct();
  }

  // Will hide menu for disabled plugins
  public static function canDisplayMenu($menu) {
    $plgName=(pq_substr($menu, 4))?lcfirst(pq_substr($menu, 4)):'';
    $listPlugin=Plugin::getLastVersionPluginList();
    if (!isset($listPlugin[$plgName])) return true;
    $plg=$listPlugin[$plgName];
    if ($plg->idle) return false;
    return true;
  }

  public function canDisplay() {
    return self::canDisplayMenu($this->name);
  }

  public static function getMenuNameFromPage($page) {
    if (pq_substr($page, 0, 27)=='objectMain.php?objectClass=') {
      $class=pq_substr($page, 27);
      if (pq_strpos($class, '&')>0) $class=pq_substr($class, 0, pq_strpos($class, '&'));
      return $class;
    } else {
      $class=pq_str_replace('ViewMain.php', '', $page);
      $class=pq_str_replace('Main.php', '', $class);
      $class=pq_str_replace('.php', '', $class);
      $class=pq_str_replace('../view/', '', $class);
      $class=pq_ucfirst($class);
      return $class;
    }
  }

  public static function drawAllNewGuiMenus($defaultMenu, $historyTable, $idFavoriteRow, $isAnotherBar=false) {
    $isNotificationSystemActiv=isNotificationSystemActiv();
    $isLanguageActive=(Parameter::getGlobalParameter('displayLanguage')=='YES')?true:false;
    // $displaySubTask=(Module::isModuleActive('moduleTodoList'))?true:false; //Parameter::getGlobalParameter('activateSubtasksManagement')=='YES'
    $customMenu=new MenuCustom();
    $obj=new Menu();
    $where=null;
    $menuList=array();
    if ($defaultMenu=='menuBarCustom') {
      $customMenuArray=$customMenu->getSqlElementsFromCriteria(array('idUser'=>getSessionUser()->id, 'idRow'=>$idFavoriteRow), false, null, 'sortOrder');
      // $where = "idUser=".getSessionUser()->id." and idRow != ".$idFavoriteRow;
      // $otherCustomArray = $customMenu->getSqlElementsFromCriteria(null, false, $where);
      $customArray=array();
      $reportArray=array();
      foreach ($customMenuArray as $custom) {
        if (pq_trim(pq_strpos($custom->name, 'menu'))=='') {
          if (!isset($reportArray[$custom->sortOrder])) {
            $reportArray[$custom->sortOrder]=$custom->name;
          } else {
            $reportArray[]=$custom->name;
          }
        } else {
          if (!isset($customArray[$custom->sortOrder])) {
            $customArray[$custom->sortOrder]=$custom->name;
          } else {
            $customArray[]=$custom->name;
          }
        }
      }
      $where="name in ('" . implode("','", $customArray) . "')";
      $menuList=$obj->getSqlElementsFromCriteria(null, false, $where);
      if (!empty($reportArray)) {
        $clause="name in ('" . implode("','", $reportArray) . "')";
        $report=new Report();
        $reportList=$report->getSqlElementsFromCriteria(null, false, $clause);
      }
      $menuListOrder=array();
      foreach ($customArray as $sortOrder=>$name) {
        foreach ($menuList as $menu) {
          if ($menu->name==$name) {
            $menuListOrder[$sortOrder]=$menu;
          }
        }
      }
      if (!empty($reportArray)) {
        foreach ($reportArray as $sortOrder=>$name) {
          foreach ($reportList as $report) {
            if ($report->name==$name) {
              $menuListOrder[$sortOrder]=$report;
            }
          }
        }
      }
      $menuList=$menuListOrder;
      ksort($menuList);
      $customMenuArray=$customArray;
    } else if ($defaultMenu=='menuBarRecent') {
      $customMenuArray=$customMenu->getSqlElementsFromCriteria(array('idUser'=>getSessionUser()->id), false, null, 'sortOrder');
      $customArray=array();
      foreach ($customMenuArray as $custom) {
        array_push($customArray, $custom->name);
      }
      $customMenuArray=$customArray;

      $historyTable=pq_explode(',', $historyTable);
      $reverseArray=array_reverse($historyTable);
      $where=($reverseArray)?"name in ('" . implode("','", $reverseArray) . "')":"";
      $menuList=($where)?$obj->getSqlElementsFromCriteria(null, false, $where):array();
      $sortHistoryTable=array();
      foreach ($reverseArray as $name) {
        foreach ($menuList as $menu) {
          if ($menu->name==$name) {
            $sortHistoryTable[$menu->name]=$menu;
            break;
          }
        }
      }
      $menuList=$sortHistoryTable;
    }
    $pluginObjectClass='Menu';
    $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
    foreach ($lstPluginEvt as $script) {
      require $script; // execute code
    }
    // $lastType='';
    foreach ($menuList as $menu) {
      if (get_class($menu)=='Menu' or $defaultMenu=='menuBarRecent') {
        if (!$isLanguageActive and $menu->name=="menuLanguage") {
          continue;
        }
        // if(!$displaySubTask and $menu->name=="menuViewAllSubTask" ){ continue; }
        if (!$isNotificationSystemActiv and pq_strpos($menu->name, "Notification")!==false) {
          continue;
        }
        if (!$menu->canDisplay()) {
          continue;
        }
        if (securityCheckDisplayMenu($menu->id, pq_substr($menu->name, 4))) {
          Menu::drawNewGuiMenu($menu, $defaultMenu, $customMenuArray, false, $isAnotherBar, $idFavoriteRow);
          // $lastType=$menu->type;
        }
      } else {
        $menuTestRigthAcces=SqlElement::getSingleSqlElementFromCriteria('menu', array('name'=>'menuReports'));
        if (!$menuTestRigthAcces->canDisplay()) {
          continue;
        }
        if (securityCheckDisplayMenu($menuTestRigthAcces->id, pq_substr($menuTestRigthAcces->name, 4))) {
          Menu::drawNewGuiMenu($menu, $defaultMenu, $reportArray, true, false, $idFavoriteRow);
        }
      }
    }
  }

  public static function drawNewGuiMenu($menu, $defaultMenu, $customMenuArray, $isReportMenu=false, $isAnotherBar=false, $idFavoriteRow=null) {
    $drawMode=Parameter::getUserParameter('menuBarTopMode');
    if (!$drawMode) $drawMode='ICONTXT';
    $marginTop='margin-top: 3px;';
    if ($drawMode!='ICON') $marginTop='margin-top: 7px;';
    $style='width:auto;height:100%;padding:5px 10px 5px 10px !important;color: var(--color-dark);filter:unset !important;white-space:nowrap;';
    if ($isReportMenu==true) {
      $cat=$menu->idReportCategory;
      $menuName=$menu->file;
      $nameSubstr=(pq_strpos($menuName, '.php')!==false)?pq_substr($menuName, 0, pq_strpos($menuName, '.php')):$menuName;
      $referTo=pq_trim($menu->referTo);
      $nameSubstrFull=''; // pq_ucfirst(pq_substr($nameSubstr,0,-4));
      $lstIdReports='';
      if ($referTo!='') {
        // $idReports=SqlList::getListWithCrit("Report","idReportCategory =$cat and referTo='$referTo'","id");
        $idReports=SqlList::getListWithCrit("Report", "(referTo='$referTo' or file like '$referTo.php%')", "id");
        $lstIdReports=implode(',', $idReports);
      } else {
        $idReports=SqlList::getListWithCrit("Report", "(referTo='$nameSubstr' or file like '$nameSubstr.php%')", "id");
        if (count($idReports)>1) {
          $nameSubstrFull=$nameSubstr; // pq_ucfirst(pq_substr($nameSubstr,0,-4));
          $lstIdReports=implode(',', $idReports);
        }
      }

      $menuClass=' menuBarItem ';
      if (in_array($menu->name, $customMenuArray)) $menuClass.=' menuBarCustom';
      $class='Reports';
      $menuName=i18n($menu->name);
      $menuId=$menu->name;
      $ReportCategory=SqlList::getNameFromId('ReportCategory', $menu->idReportCategory, false);
      if ($ReportCategory=='reportCategoryObjectList') {
        $menuName=$menu->name;
        $menuId='ReportObjectList' . $menu->id;
      }
      echo '<div id="dndItem' . $menuId . '_' . $idFavoriteRow . '" name="dndItem' . $menuId . '" title="' . $menuName . '" class="dojoDndItem itemBar" dndType="menuBar" style="float:left;' . $marginTop . '">';
      echo '<div class="' . $menuClass . '" style="' . $style . '" id="iconMenuBar' . $menuId . '_' . $idFavoriteRow . '" ';
      echo 'oncontextmenu="event.preventDefault();hideReportFavoriteTooltip(0,\'' . $idFavoriteRow . '\' );';
      if ($defaultMenu=='menuBarRecent' and !in_array($menu->name, $customMenuArray) or ($defaultMenu=='menuBarCustom')) {
        echo 'showFavoriteTooltip(\'' . $menuId . '\', \'' . $idFavoriteRow . '\');"';
      } else {
        echo '"';
      }
      echo ' onMouseLeave="hideFavoriteTooltip(0,\'' . $menuId . '\',\'' . $idFavoriteRow . '\');"';

      echo 'onClick="loadMenuReportDirect(\'' . $menu->idReportCategory . '\',\'' . $menu->id . '\',\'' . $lstIdReports . '\',\'' . $nameSubstrFull . '\');stockHistory(\'Reports\',\'repId=' . $menu->id . '\', \'Reports\');refreshSelectedMenuLeft(\'' . $menuId . '\');showMenuBottomParam(\'' . $class . '\',\'true\');">';
      Menu::drawIconMenuNewGui($drawMode, $class, $menu, true);
      $class=$menuId;
      Menu::drawNewGuiDialogueAddRemoveFav($menu, $customMenuArray, $defaultMenu, $class, false, true, false, $idFavoriteRow);
      echo '</div>';
      echo '</div>';
    } else {
      $menuName=$menu->name;
      $menuClass=' menuBarItem ' . $menu->menuClass;
      if (in_array($menu->name, $customMenuArray)) $menuClass.=' menuBarCustom';
      $idMenu=$menu->id;
      $class=pq_substr($menuName, 4);
      if ($menu->type=='item') {
        echo '<div id="dndItem' . $menuName . '_' . $idFavoriteRow . '" name="dndItem' . $menuName . '" title="' . i18n($menuName) . '" class="dojoDndItem itemBar" dndType="menuBar" style="float:left;' . $marginTop . '">';
        echo '<div class="' . $menuClass . '" style="' . $style . '" id="iconMenuBar' . $class . '_' . $idFavoriteRow . '" ';
        echo 'onClick="hideReportFavoriteTooltip(0,\'' . $idFavoriteRow . '\');loadMenuBarItem(\'' . $class . '\',\'' . htmlEncode(i18n($menuName), 'quotes') . '\',\'bar\');refreshSelectedMenuLeft(\'' . $menuName . '\');showMenuBottomParam(\'' . $class . '\',\'false\');"';
        echo 'oncontextmenu="event.preventDefault();hideReportFavoriteTooltip(0,\'' . $idFavoriteRow . '\');';
        if ($defaultMenu=='menuBarRecent' and !in_array($menuName, $customMenuArray) or ($defaultMenu=='menuBarCustom')) {
          echo 'showFavoriteTooltip(\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
        } else {
          echo '"';
        }
        if ($menuName=='menuReports' and isHtml5()) {
          echo ' onMouseEnter="showReportFavoriteTooltip(\'' . $idFavoriteRow . '\');hideFavoriteTooltip(0,\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
          echo ' onMouseLeave="hideReportFavoriteTooltip(0,\'' . $idFavoriteRow . '\');hideFavoriteTooltip(0,\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
        } else {
          echo ' onMouseLeave="hideFavoriteTooltip(0,\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
        }
        echo '>';
        Menu::drawIconMenuNewGui($drawMode, $class, $menu);
        Menu::drawNewGuiDialogueAddRemoveFav($menu, $customMenuArray, $defaultMenu, $class, $menuName, false, $isAnotherBar, $idFavoriteRow);
        echo '</div>';
        echo '</div>';
      } else if ($menu->type=='plugin') {
        echo '<div id="dndItem' . $menuName . '" name="dndItem' . $menuName . '" title="' . i18n($menuName) . '" class="dojoDndItem itemBar" dndType="menuBar" style="float:left;' . $marginTop . '">';
        echo '<div class="' . $menuClass . '" style="' . $style . '" id="iconMenuBar' . $class . '"';
        echo 'oncontextmenu="event.preventDefault();hideReportFavoriteTooltip(0,\'' . $idFavoriteRow . '\');showFavoriteTooltip(\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
        echo ' onMouseLeave="hideFavoriteTooltip(0,\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
        echo 'onClick="loadMenuBarPlugin(\'' . $class . '\',\'' . htmlEncode(i18n($menuName), 'quotes') . '\',\'bar\');refreshSelectedMenuLeft(\'' . $menuName . '\');showMenuBottomParam(\'' . $class . '\',\'false\');">';
        Menu::drawIconMenuNewGui($drawMode, $class, $menu);
        Menu::drawNewGuiDialogueAddRemoveFav($menu, $customMenuArray, $defaultMenu, $class, false, false, false, $idFavoriteRow);
        echo '</div>';
        echo '</div>';
      } else if ($menu->type=='object') {
        if (securityCheckDisplayMenu($idMenu, $class)) {
          echo '<div id="dndItem' . $menuName . '_' . $idFavoriteRow . '" name="dndItem' . $menuName . '" title="' . i18n('menu' . $class) . '" class="dojoDndItem itemBar" dndType="menuBar" style="float:left;' . $marginTop . '">';
          echo '<div class="' . $menuClass . '" style="' . $style . '" id="iconMenuBar' . $class . '_' . $idFavoriteRow . '" ';
          echo 'oncontextmenu="event.preventDefault();hideReportFavoriteTooltip(0, \'' . $idFavoriteRow . '\');';
          if ($defaultMenu=='menuBarRecent' and !in_array($menu->name, $customMenuArray) or ($defaultMenu=='menuBarCustom')) {
            echo 'showFavoriteTooltip(\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
          } else {
            echo '"';
          }
          echo ' onMouseLeave="hideFavoriteTooltip(0,\'' . $class . '\',\'' . $idFavoriteRow . '\');"';
          echo 'onClick="loadMenuBarObject(\'' . $class . '\',\'' . htmlEncode(i18n($menuName), 'quotes') . '\',\'bar\');refreshSelectedMenuLeft(\'' . $menuName . '\');showMenuBottomParam(\'' . $class . '\',\'true\');">';
          Menu::drawIconMenuNewGui($drawMode, $class, $menu);
          Menu::drawNewGuiDialogueAddRemoveFav($menu, $customMenuArray, $defaultMenu, $class, false, false, false, $idFavoriteRow);
          echo '</div>';
          echo '</div>';
        }
      }
    }
  }

  public static function drawIconMenuNewGui($drawMode, $class, $menu, $isReport=false) {
    if ($drawMode=='ICON') {
      $iconColor=getIconColor($class);
      if ($isReport==false and $menu->type=='plugin') {
        echo '<img src="../view/css/images/icon' . $class . '22.png" />';
      } else {
        echo '<div class="icon' . $class . '22 icon' . $class . ' iconSize22 imageColorNewGui" style="width:22px;height:22px;'.$iconColor.'"></div>';
      }
    } else if ($drawMode=='TXT') {
      $textColor=getTextColor($class);
      echo '<span style="'.$textColor.'">'.i18n($menu->name).'</span>';
    } else if ($drawMode=='ICONTXT') {
      $iconColor=getIconColor($class);
      $textColor=getTextColor($class);
      echo '<table><tr>';
      if ($isReport==false and $menu->type=='plugin') {
        echo '<td><img src="../view/css/images/icon' . $class . '22.png" /></td>';
      } else {
        echo '<td><div class="icon' . $class . '16 icon' . $class . ' iconSize16 imageColorNewGui" style="width:16px;height:16px;'.$iconColor.'"></div></td>';
      }
      $menuName=i18n($menu->name);
      if ($isReport) {
        $ReportCategory=SqlList::getNameFromId('ReportCategory', $menu->idReportCategory, false);
        if ($ReportCategory=='reportCategoryObjectList') $menuName=$menu->name;
      }
      echo '<td style="padding-left:5px;'.$textColor.'">' . $menuName . '</td>';
      echo '</tr></table>';
    }
  }

  public static function drawNewGuiDialogueAddRemoveFav($menu, $customMenuArray, $defaultMenu, $class, $menuName=false, $isReport=false, $isAnotherBar=false, $idFavoriteRow=null) {
    $currentBar=Parameter::getUserParameter('defaultMenu');
    if (($isReport==false and $menu->type=='item' and $menuName=='menuReports' and isHtml5()) and (($isAnotherBar and $currentBar=='menuBarCustom') or !$isAnotherBar)) {
      echo '<div class="comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="listFavoriteReports_' . $idFavoriteRow . '" name="listFavoriteReports_' . $idFavoriteRow . '" style="position:absolute;top:22px;left:0px;height: 0px; overflow: hidden; ">';
      echo '<div dojoType="dijit.TooltipDialog" id="favoriteReports_' . $idFavoriteRow . '" style="position:absolute;"href="../tool/refreshFavoriteReportList.php' . Security::addTokenIndexToUrl('?') . '&idFavoriteRow=' . $idFavoriteRow . '" onMouseEnter="clearTimeout(closeFavoriteReportsTimeout);"
              onMouseLeave="hideReportFavoriteTooltip(200,\'' . $idFavoriteRow . '\')" onDownloadEnd="checkEmptyReportFavoriteTooltip(\'' . $idFavoriteRow . '\')" onShow="favoriteReportsTooltipReposition(\'listFavoriteReports_' . $idFavoriteRow . '\');">';
      Favorite::drawReportList($idFavoriteRow);
      echo ' </div></div>';
    }

    if ($defaultMenu=='menuBarRecent' and !in_array($menu->name, $customMenuArray) or ($defaultMenu=='menuBarCustom')) {
      echo '<div class="comboButtonInvisible" dojoType="dijit.form.DropDownButton"id="addFavorite' . $class . '_' . $idFavoriteRow . '" name="addFavorite' . $class . '" style="position:absolute;top:22px;left:20px;height: 0px; overflow: hidden; ">';
      echo '<div dojoType="dijit.TooltipDialog" id="dialogFavorite' . $class . '_' . $idFavoriteRow . '" style="cursor:pointer;"onMouseEnter="clearTimeout(closeFavoriteTimeout);"onMouseLeave="hideFavoriteTooltip(200,\'' . $class . '\',\'' . $idFavoriteRow . '\')"';

      if (!in_array($menu->name, $customMenuArray)) {
        $mode="add";
        $classAttr="menuBar_add_Fav";
        $lib=i18n('customMenuAdd');
      } else {
        $mode="remove";
        $classAttr="menuBar_remove_Fav";
        $lib=i18n('customMenuRemove');
      }
      echo 'onClick="addRemoveFavMenuLeft(\'div' . (($isReport==true)?pq_ucfirst($menu->name):$menu->name) . '\', \'' . $menu->name . '\',\'' . $mode . '\',\'' . (($isReport==true)?"reportDirect":"menu") . '\', \'' . $idFavoriteRow . '\');">';
      echo '<div class="' . $classAttr . '" style="white-space:nowrap;padding-right:10px;">' . $lib . '</div>';
      echo '</div></div>';
    }
  }

}
?>