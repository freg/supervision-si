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
 * Client is the owner of a project.
 */ 
require_once('_securityCheck.php'); 
class ColumnSelector extends SqlElement {

	// extends SqlElement, so has $id
	public $id;    // redefine $id to specify its visible place
	public $scope;
	public $objectClass;
	public $idUser;
	public $field;
	public $attribute;
	public $hidden;
	public $sortOrder;
	public $widthPct;
	public $name;
	public $formatter;
	public $subItem;
	public $_from;
	public $_displayName;

	public $_noHistory=true; // Will never save history for this object
	
	private static $cachedLists=array();
	private static $allFields=true; // Keep it to false as long as addAllFields() is not fiabilized
	/** ==========================================================================
	 * Constructor
	 * @param $id Int the id of the object in the database (null if not stored yet)
	 * @return void
	 */
	function __construct($id = NULL, $withoutDependentObjects=false) {
		parent::__construct($id,$withoutDependentObjects);
	}


	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
		parent::__destruct();
	}

	// ============================================================================**********
	// GET STATIC DATA FUNCTIONS
	// ============================================================================**********
	public static function getColumnsList($classObj) {
		// scope = "list"
// 		if (isset(self::$cachedLists['list#'.$classObj])) {
// 			return self::$cachedLists['list#'.$classObj];
// 		}
		if (sessionValueExists('list#'.$classObj)) {
		  return getSessionValue('list#'.$classObj);
		}
		global $hideScope,$contextForAttributes; 
		$hideScope='column';
		// retrieve from database, in correct order
		$user=getSessionUser();
		$obj=new $classObj();
		$extraHiddenFields=$obj->getExtraHiddenFields('*','*');
		if (isset($extraHiddenFields['id'])) unset($extraHiddenFields['id']);
		if (isset($extraHiddenFields['name'])) unset($extraHiddenFields['name']);
		if ($classObj == 'Project' && Module::isModuleActive('moduleTechnicalProgress')) {
		  if (!isset($obj->ProjectPlanningElement)) {
		    $obj->ProjectPlanningElement = new ProjectPlanningElementMain();
		  }
		  $obj->ProjectPlanningElement->unitWeight = 1;
		}
		if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
		$cs=new ColumnSelector();
		$crit=array('scope'=>'list', 'objectClass'=>$classObj, 'idUser'=>$user->id);
		$csList=$cs->getSqlElementsFromCriteria($crit, false, null, 'sortOrder asc');
		$result=array();
		foreach ($csList as $cs) {
		  if (! SqlElement::isVisibleField($cs->attribute)) {
        continue;
      }
      if ($obj->isAttributeSetToField($cs->attribute, 'notInList')) {
        continue;
      }
     if ( ( $obj->isAttributeSetToField($cs->attribute, 'hidden') or in_array($cs->attribute,$extraHiddenFields) ) and $cs->attribute!='id' and $cs->attribute!='name') {
        continue;  
      }
      $cs->_name=$cs->attribute;
      $dispObj=$obj;
      $hidden=$extraHiddenFields;
      if ($cs->subItem) {
      	$fromObj='obj'.$cs->subItem;
      	if (! isset($$fromObj)) {
      		$$fromObj=new $cs->subItem();      		
      	}
      	$dispObj=$$fromObj;
      	$hiddenObj='hidden'.$cs->subItem;
      	if (! isset($$hiddenObj)) {
      	  $$hiddenObj=$dispObj->getExtraHiddenFields();
      	}
      	$hidden=$$hiddenObj;
      }     
      if (in_array($cs->attribute,$hidden) and $cs->attribute!='id' and $cs->attribute!='name') {
        continue;
      }
      $cs->_displayName=$dispObj->getColCaption($cs->_name);
		  if (pq_substr($cs->attribute,0,9)=='idContext' and pq_strlen($cs->attribute)==10) {
		    $ctx=new ContextType(pq_substr($cs->attribute,-1));
        $cs->_displayName=$ctx->name;
		  } else if (pq_substr($cs->attribute,0,9)=='mandatory' and $contextForAttributes=='global') { // add caption that appears after checkbox for fields with shorten name
        $found=0;
        $nextCaption=null;
        foreach ($obj->getFieldsList() as  $tmpcol) {
          if ($tmpcol==$cs->attribute) {
            $found=1;
            continue;
          } else if ($found and pq_substr($tmpcol,0,5)=='_lib_') {
            $next=$tmpcol;
            $nextCaption=i18n(pq_substr($tmpcol, 5));
            break;
          }
        }
        if ($nextCaption) {
          $cs->_displayName.=' ('.$nextCaption.')';
        }
      }
      $cs->_from=$cs->subItem;
			$result[$cs->attribute]=$cs;
		}

		// retrieve (complete) from layout
		$cpt=count($result);
		$layout=$obj->getStaticLayout();
		$dom = new DOMDocument();
		$dom->loadHTML($layout);
		$domx = new DOMXPath($dom);
		$entries = $domx->evaluate("//th");
		Sql::beginTransaction();
		$lastFrom=null;
		$lastHiddenFrom=null;
		foreach ($entries as $entry) {
			$field=$entry->getAttribute("field");
			$from=$entry->getAttribute("from");
			if ($from) {
			  if ($lastFrom and $lastFrom==$from) {
			    $extraHiddenFieldsTest=$lastHiddenFrom;
			  } else {
  			  $objFrom=New $from();
  			  $extraHiddenFieldsTest=$objFrom->getExtraHiddenFields('*','*');
  			  $lastHiddenFrom=$extraHiddenFieldsTest;
  			  $lastFrom=$from;
			  }
			} else {
			  $extraHiddenFieldsTest=$extraHiddenFields;
			}
			$attribute=$field;
      if (pq_substr($attribute,0,4)=="name" and $attribute!="name") {$attribute='id'.pq_substr($attribute,4);}
      if (pq_substr($attribute,0,9)=="colorName") {$attribute='id'.pq_substr($attribute,9);}     
      if (pq_substr($attribute,-8)=="Sortable") {$attribute=pq_substr($attribute,0,pq_strlen($attribute)-8);} 
      if (($obj->isAttributeSetToField($attribute, 'hidden') or in_array($attribute,$extraHiddenFieldsTest) ) and $attribute!='id' and $attribute!='name') {
        continue;
      }
      if ($obj->isAttributeSetToField($attribute, 'notInList')) {
        continue;
      }
			$cpt++;
			if (pq_array_key_exists($attribute, $result)) {
				$cs=$result[$attribute];
			} else {
				$cs=new ColumnSelector();
				$cs->scope="list";
				$cs->objectClass=$classObj;
				$cs->idUser=$user->id;
				$cs->field=$field;
				$cs->attribute=$attribute;
				$cs->hidden=(pq_strtolower($entry->getAttribute("hidden"))=="true")?1:0;
				$cs->sortOrder=$cpt;
				$cs->widthPct=pq_str_replace('%','',$entry->getAttribute("width"));
			}
			$cs->name=pq_str_replace(array('# ','${','}'), array('','',''), $entry->nodeValue);
			$cs->_displayName=i18n('col'.pq_ucfirst($cs->name));
			if ($field=='name' and (!property_exists($obj,'_isNameTranslatable') or !$obj->_isNameTranslatable)) {
			  $cs->formatter='formatUpperName';
			}else if ($field=='sortOrder') { 
			  $cs->formatter='numericFormatter';
		    }else {
			  $cs->formatter=$entry->getAttribute("formatter");
			}
			$cs->_from=$entry->getAttribute("from");
			$cs->subItem=$cs->_from;
			if (!$cs->id) { 
			  $cs->save();
			}
			$result[$attribute]=$cs;
		}
		if (self::$allFields) {
			$result=self::addAllFields($result,$obj);
		}
		if (! self::$allFields) {
			foreach ($result as $id=>$cs) {
				if (! $cs->name) {
					if ($cs->id) {
						$res=$cs->delete();
					}
					unset($result[$cs->attribute]);
				}
			}
	    }
	    if (property_exists($obj, '_Note') || property_exists($obj, '_Attachment') || property_exists($obj, '_Link')) {
	      $indicatorField = 'indicatorFileNoteLink';
	      if (!pq_array_key_exists($indicatorField, $result)) {
	        $cs = new ColumnSelector();
	        $cs->scope = 'list';
	        $cs->objectClass = $classObj;
	        $cs->idUser = $user->id;
	        $cs->field = $indicatorField;
	        $cs->attribute = $indicatorField;
	        $cs->hidden = 1;
	        $cs->sortOrder = count($result) + 1;
	        $cs->widthPct = 5;
	        $cs->name = 'indicatorFileNoteLink';
	        $cs->_displayName = i18n('colIndicatorFileNoteLink');
	        $cs->formatter = 'indicatorFormatter';
	        $cs->_from = null;
	        $cs->subItem = null;
	        $cs->save();
	        $result[$indicatorField] = $cs;
	      }
	    }
		Sql::commitTransaction();
//		self::$cachedLists['list#'.$classObj]=$result;
		setSessionValue('list#'.$classObj, $result);
		return $result;
	}

	private static function addAllFields($result, $obj, $included=false, $sourceClass=null) {
	  global $hideScope;
	  $hideScope='column';
		$fieldsArray=$obj->getFieldsArray();
		$extrahiddenFields=$obj->getExtraHiddenFields('*','*');
		if (method_exists($obj, 'setAttributes')) $obj->setAttributes();
		$user=getSessionUser();
		$cpt=count($result);
		$resultTemp=array();
		foreach($obj as $col => $val) {
		  if (pq_array_key_exists($col,$result)) {
        continue;
      }
			if ( $included and ($col=='id' or $col=='refId' or $col=='refType' or $col=='refName') ) {
				continue;
			}
			if ($obj->isAttributeSetToField($col, 'notInList')) {
			  continue;
			}
			if (pq_substr($col,0,1)=='_') {
				continue;
			}
			//gautier #6564
			if (is_object($val)) {
			  $resultTemp=array_merge_preserve_keys($resultTemp,self::addAllFields($result, $val, true, get_class($obj)));
			  continue;
			}
			if ($obj->isAttributeSetToField($col,'hidden') or $obj->isAttributeSetToField($col,'noList') 
			 or $obj->isAttributeSetToField($col,'calculated')) {
				continue;
			}
			if (in_array($col,$extrahiddenFields)) {
			  continue;
			}
			if ($col=="password" or $col=="Origin") {
				continue;
			}
			if (! SqlElement::isVisibleField($col)) {
				continue;
			}
			$dataType = $obj->getDataType($col);
			$dataLength = $obj->getDataLength($col);
			if ((($dataType=='varchar' and $dataLength>400) or $dataType=='text') and $col!='tags') {
				continue;
			}
			//$cpt++;
			$cs=new ColumnSelector();
			$cs->scope="list";
			if ($included) {
				$cs->_from=get_class($obj);
				$cs->subItem=$cs->_from;
				$cs->objectClass=$sourceClass;
			} else {
				$cs->objectClass=get_class($obj);
			}
			$cs->idUser=$user->id;
			$cs->field=$col;
			if (pq_substr($cs->field,0,2)=='id' and pq_strlen($cs->field)>2 and pq_substr($col,2,1)==pq_strtoupper(pq_substr($col,2,1)) ) {
				$cs->field='name'.pq_substr($cs->field,2);
			}
			$cs->attribute=$col;
			//$cs->sortOrder=$cpt;
			$cs->widthPct=5;
			$cs->name=$col;
			$cs->_displayName=$obj->getColCaption($col);
			if (pq_substr($cs->attribute,0,9)=='idContext') {
        $ctx=new ContextType(pq_substr($cs->attribute,-1));
        $cs->_displayName=$ctx->name;
      } 
			$cs->formatter='';
			$cs->hidden=1;
			if ($col=='id') {
				$cs->formatter="numericFormatter";
		  } else if ($col=='tags') {
        $cs->formatter="tagFormatter";
        $cs->widthPct=10;
		  } else if ($col=='icon') {
        $cs->formatter="iconFormatter";
        $cs->widthPct=5;
			} else if ($dataType=='date') {
				$cs->formatter="dateFormatter";
				$cs->widthPct=10;
			} else if ($dataType=='datetime') {
        $cs->formatter="dateTimeFormatter";
        $cs->widthPct=10;
      } else if ($dataType=='time') {
        $cs->formatter="timeFormatter";
        $cs->widthPct=10;
			} else if ($col=='color' and $dataLength == 7 ) {
				$cs->formatter="colorFormatter";
			} else if ($dataType=='int' and $dataLength==1) {
				$cs->formatter="booleanFormatter";
			//} else if (pq_substr($col,0,2)=='id' and $dataType=='int' and pq_strlen($col)>2 and pq_substr($col,2,1)==pq_strtoupper(pq_substr($col,2,1)) ) {
			} else if (isForeignKey($col, $obj)) {
				$idClass=pq_substr(foreignKeyWithoutAlias($col),2);
				if (SqlElement::class_exists($idClass)) {
					//$idObj=new $IdClass;
				  $cs->formatter="nameFormatter";
				  if (Affectable::isAffectable($idClass)) {
					  $cs->formatter="thumbName22";
					}
					if (pq_strpos($col,'__id')>0) {
					  $cs->formatter="nameFormatter";
					} else if(property_exists($idClass, 'color')) {
						$cs->field='color'.pq_ucfirst($cs->field);
	          $cs->formatter="colorNameFormatter";
	        } else if(property_exists($idClass, '_isNameTranslatable')) {
	          $cs->formatter="translateFormatter";
	        } else {
	          //$cs->formatter="";
	        }
	        $cs->widthPct=10;
				}
			} else if ($dataType=='int' or $dataType=='decimal') {
				if (pq_strtolower(pq_substr($col,-8))=='progress' or pq_strpos($col,'Pct')!=false or pq_substr($col, -4, 4)=='Rate') {
					 $cs->formatter="percentFormatter";
				} else if (pq_strtolower(pq_substr($col,-4))=='work') {
					 $cs->formatter="workFormatter";
				}else if (SqlElement::isAmount($col)) {
				  if (SqlElement::isLocal($col)) $cs->formatter="costFormatterLocal";	
          else $cs->formatter="costFormatter";	
				} else if (pq_strtolower(pq_substr($col,-8))=='duration') {
				  $cs->formatter="durationFormatter";
				} else {
				  $cs->formatter="numericFormatter";
				}
			}
			$resultTemp[replace_accents($obj->getColCaption($col)).'-'.$cs->attribute]=$cs;
		}
		if ($included) return $resultTemp;
		ksort($resultTemp); 
		foreach ($resultTemp as $temp) {
		  $cpt++;
		  $temp->sortOrder=$cpt;
		  $res=$temp->save();
		  $result[$temp->attribute]=$temp;
		}
		
		return $result;
	}
}
?>
