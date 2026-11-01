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
 * Habilitation defines right to the application for a menu and a profile.
 */
require_once('_securityCheck.php');

class Importable extends SqlElement {

	// extends SqlElement, so has $id
	public $id;    // redefine $id to specify its visible place
	public $name;

	public $_isNameTranslatable = true;

	public static $importResult;
	public static $cptTotal;
	public static $cptDone;
	public static $cptUnchanged;
	public static $cptCreated;
	public static $cptModified;
	public static $cptRejected;
	public static $cptInvalid;
	public static $cptError;
	//
	public static $cptOK;
	public static $cptWarning;

	private static $_importInProgress=false; 
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
	// MISCELLANOUS FUNCTIONS
	// ============================================================================**********
	public static function startImport() {
	  self::$_importInProgress=true;
	}
	public static function stopImport() {
	  self::$_importInProgress=false;
	}
	public static function importInProgress() {
	  if (self::$_importInProgress===true) {
	    return true;
	  } else {
	    return false;
	  }
	}
	
	public static function import($fileName, $class) {
	  $idUser = getCurrentUserId();
	  if (is_object($idUser)) { $idUser = $idUser->id; }
	  require_once '../model/ImportProgress.php';
	  ImportProgress::start($idUser);
	  try {
	    $result = self::doImport($fileName, $class);
	  } finally {
	    ImportProgress::finish($idUser, self::$importResult ? self::$importResult : '', $class, $fileName, 'done');
	  }
	  return $result;
	}
	
	
	public static function doImport($fileName, $class){
	  $fileName=pq_str_replace('\\','/',$fileName);
	  $fileName=pq_str_replace('//','/',$fileName);
	  $baseFileName=basename($fileName);
	  self::startImport();
		require_once '../external/XLSXReader/XLSXReader.php';
		$extension=pathinfo($fileName, PATHINFO_EXTENSION); // get the real file extension
		if (isset($_REQUEST['fileType'])) {
		  $fileType=$_REQUEST['fileType'];
		  $fileType=preg_replace('/[^a-zA-Z0-9-_]/','', pq_nvl($fileType)); // only allow [a-z,A-Z,-,_] for file extension
		} else {
			$fileType=$extension;
		}
		SqlElement::unsetCurrentObject(); // Clear last accessed item : otherwise history will get wrong
		SqlElement::setSaveConfirmed(); // PBER #10335
		
		if($extension!=$fileType){
			errorLog("ERROR - Type : File Type and Type selected are not consistent");
			errorLog("File Name : ".$baseFileName);
			errorLog("Type Selected : ".$fileType);
			$msg=i18n('errorImportFormat');
			self::$importResult=$msg;
			self::stopImport();
			return $msg;
		}
		switch($extension){
			case "csv":
				traceLog( "Import : File type CSV");
				traceLog("File Name : ".$baseFileName);
				break;
			case "xlsx":
				traceLog( "Import : File type XSLX");
				traceLog("File Name : ".$baseFileName);
				break;
			default:
				errorLog("ERROR - File Type not recognized");
				errorLog("File Name : ".$baseFileName);
				$msg='<b>ERROR - File Type not recognized</b><br/>Import aborted<br/>Contact your administrator';
				self::$importResult=$msg;
				self::stopImport();
				return $msg;
				break;
		}
		// Control that mbsting is available
		if (! function_exists('mb_detect_encoding')) {
			errorLog("ERROR - mbstring not enabled - Import cancelled");
			$msg='<b>Error - mbstring is not enabled</b><br/>Import aborted<br/>Contact your administrator';
			self::$importResult=$msg;
			self::stopImport();
			return $msg;
		}
		SqlList::cleanAllLists(); // Added for Cron mode : as Cron is never stopped, Static Lists must be freshened
		projeqtor_set_time_limit(3600); // 60mn
		self::$cptTotal=0;
		self::$cptDone=0;
		self::$cptUnchanged=0;
		self::$cptCreated=0;
		self::$cptModified=0;
		self::$cptRejected=0;
		self::$cptInvalid=0;
		self::$cptError=0;
		self::$cptOK=0;
		self::$cptWarning=0;
		if (! SqlElement::class_exists($class)) {
			self::$importResult="Cron error : class '$class' is unknown";
			self::$cptError=1;
			self::$cptRejected=1;
			self::stopImport();
			return "ERROR";
		}
		switch($extension){
		  case "csv":
		    $data=Importable::importCSV($fileName);
		    break;
		  case "xlsx":
		    $data=Importable::importXLSX($fileName);
		    date_default_timezone_set('UTC');
		    break;
		  default:
		    errorLog("ERROR - File Type not recognized");
		    errorLog("File Name : ".$fileName);
		    $msg='<b>ERROR - File Type not recognized</b><br/>Import aborted<br/>Contact your administrator';
		    self::$importResult=$msg;
		    self::stopImport();
		    return $msg;
		    break;
		}
		$documentAndVersion=false;
		if ($class=='DocumentVersion' or $class=='Document') {
		  $firstLine=reset($data);
		  foreach ($firstLine as $idx=>$caption) {
		    if (pq_strpos($caption,'(DocumentVersion)')>0) {
		      $documentAndVersion='(DocumentVersion)';
		      break;
		    } else if (pq_strpos($caption,'('.i18n('DocumentVersion').')')>0) {
		      $documentAndVersion='('.i18n('DocumentVersion').')';
		      break;
		    }
		  }
		  if ($documentAndVersion) {
		    $class='Document';
		  }
		}
		$obj=new $class();
		if ($documentAndVersion) {
		  $obj->DocumentVersion=new DocumentVersion();
		}
		$captionArray=array();
		$captionObjectArray=array();
		$objectArray=array();
		$titleObject=array();
		$noImport=array();
		$idArray=array();
		foreach ($obj as $fld=>$val) {
			if (is_object($val)) {
				$objectArray[$fld]=$val;
				foreach ($val as $subfld=>$subval){
					$capt=pq_trim($val->getColCaption($subfld));
					if ($documentAndVersion) {
					  $capt=$capt.' '.$documentAndVersion;
					}
					if ( ($subfld!='id' or $documentAndVersion) and pq_substr($capt,0,1)!='[' and ! isset($captionArray[$capt]) ) {
						$captionArray[$capt]=$subfld;
						$captionObjectArray[$capt]=$fld;
					}
				}
			} else {
				$capt=pq_trim($obj->getColCaption($fld));
				if (pq_substr($fld,0,9)=='idContext' and pq_strlen($fld)==10) {
                  $ctx=new ContextType(pq_substr($fld,-1));
                  $val=$ctx->name;
                  $captionArray[$val]=$fld;
                } else if (pq_substr($capt,0,1)!='[' ) {
					$captionArray[$capt]=$fld;
				}
			}
		}
		if ($documentAndVersion) {
		  $dv=new DocumentVersion();
		  $subObj=$dv;
		  $objectArray['DocumentVersion']=$dv;
		  foreach ($dv as $subfld=>$subval){
		    $capt=pq_trim($dv->getColCaption($subfld)).' ('.i18n('DocumentVersion').')';
		    if (pq_substr($capt,0,1)!='[' and ! isset($captionArray[$capt]) ) {
		      //$captionArray[$capt]=$subfld.' (DocumentVersion)';
		      //$captionObjectArray[$capt]=$objectArray['DocumentVersion'];
		    }
		  }
		}
		$title=null;
		$idxId=-1;
		$idxRefType=-1;
		$htmlResult="";
		$htmlResult.='<TABLE style="border: 1px solid black; border-collapse:collapse;width:98%;margin:0 auto;">';
		traceLog("Start import $class from file $baseFileName : ".(count($data)-1)." lines to import");
		$convertWork = false;
		$idUser = getSessionUser();
		if (is_object($idUser)) {
		  $idUser = $idUser->id;
		}
		foreach($data as $nbl=>$fields){
		  if ($nbl>0) traceLog(" => Import line n° $nbl");
		  if ($nbl==1) {
		    ImportProgress::update($idUser, 0, count($data)-1); 
		  }
		  if ($nbl>0 && $nbl % 5 == 0) {
		    ImportProgress::update($idUser, $nbl);
		  }
			if($nbl==0){
				$htmlResult.= "<TR>";
				$obj=new $class();
				$otherObj=null;
				if ($documentAndVersion) $otherObj=new DocumentVersion();
				foreach ($fields as $idx=>$caption) {
					$title[$idx]=pq_trim($caption);
					$title[$idx]=pq_str_replace(chr(13),'',$title[$idx]);
					$title[$idx]=pq_str_replace(chr(10),'',$title[$idx]);
					$newColCaption='';
					if(pq_stripos($title[$idx], '(h)')){
					  $newColCaption=$title[$idx];
					  $cap=pq_str_replace('(h)', '', $newColCaption);
					  $cap=pq_trim($cap);
					  $title[$idx]=$cap;
					  $convertWork=true;
					}
					$color="#A0A0A0";
					$colorNoImport="#A0A0FF";
					$colCaption=$title[$idx];
					$testTitle=pq_str_replace(' ', '', $title[$idx]);
					$testIdTitle='id'.pq_ucfirst($testTitle);
					$testCaption=$title[$idx];
					$testIdClassTitle='id'.$class.pq_ucfirst($testTitle);
					if ($testTitle and property_exists($obj,$testTitle)) { // Title is directly field id
					    $title[$idx]=$testTitle;
						$color="#000000";
						$colCaption=$obj->getColCaption($title[$idx]);
						if ($title[$idx]=='id') {
							$idxId=$idx;
						}
					    if ($title[$idx]=='refType') {
							$idxRefType=$idx;
						}
						if($newColCaption)$colCaption=$newColCaption;
					} else if ($testIdTitle and property_exists($obj,$testIdTitle)) { // Title is field id withoud the 'id' (for external reference)
					  $title[$idx]=$testIdTitle;
						$idArray[$idx]=true;
						$color="#000000";
						$colCaption=$obj->getColCaption($title[$idx]);
					} else if (pq_array_key_exists($testCaption,$captionArray) or pq_array_key_exists(pq_strtolower($testCaption),$captionArray)) {
					  $color="#000000";
						$colCaption=$testCaption;
						if (pq_array_key_exists(pq_strtolower($testCaption),$captionArray)) {$testCaption=pq_strtolower($testCaption);}
						$title[$idx]=$captionArray[$testCaption];
						if (isset($captionObjectArray[$testCaption])) {
							$titleObject[$idx]=$captionObjectArray[$testCaption];
						}
					} else {
					  foreach ($objectArray as $fld=>$subObj) {
						  if ($documentAndVersion) {
						    $testTitle=pq_trim(pq_str_replace($documentAndVersion,'',$title[$idx]));
						    $testTitle=pq_str_replace(' ', '', $testTitle);
						    $testIdTitle='id'.pq_ucfirst($testTitle);
						    $testCaption=$title[$idx];
						    $testIdClassTitle='id'.$class.pq_ucfirst($testTitle);
						  }
						  if (property_exists($subObj,$testTitle)) { // Title is directly field id
								if (!$documentAndVersion) $title[$idx]=$testTitle;
								$color="#000000";
								$titleObject[$idx]=$fld;
								$colCaption=$subObj->getColCaption($title[$idx]);							
							} else if (property_exists($subObj,$testIdTitle)) { // Title is field id withoud the 'id' (for external reference)
								if (!$documentAndVersion) $title[$idx]=$testIdTitle;
								$idArray[$idx]=true;
								$color="#000000";
								$titleObject[$idx]=$fld;
								$colCaption=$subObj->getColCaption($title[$idx]);
							} else if (pq_array_key_exists($testCaption,$captionArray) or pq_array_key_exists(pq_strtolower($testCaption),$captionArray)) {
								$color="#000000";
								$colCaption=$testCaption;
								if (pq_array_key_exists(pq_strtolower($testCaption),$captionArray)) {
									$testCaption=pq_strtolower($testCaption);
								}
								if (!$documentAndVersion) $title[$idx]=$captionArray[$testCaption];
								if (isset($captionObjectArray[$testCaption])) {
									$titleObject[$idx]=$captionObjectArray[$testCaption];
								}
								if($newColCaption)$colCaption=$newColCaption;
							}
						}
					}
					if (isset($titleObject[$idx]) and SqlElement::class_exists($titleObject[$idx]) ) {
						$subObj=new $titleObject[$idx]();
						if ($subObj->isAttributeSetToField($title[$idx], 'noImport') and $title[$idx]!='idPlanningMode') {
							$color=$colorNoImport;
							$noImport[$idx]=true;
						}
					} else {
						if ($obj->isAttributeSetToField($title[$idx], 'noImport')) {
							$color=$colorNoImport;
							$noImport[$idx]=true;
						}
					}
					$htmlResult.= '<TH class="messageHeader" style="color:' . $color . ';border:1px solid black;background-color: #DDDDDD">' . $colCaption . "</TH>";
				}
				$htmlResult.= '<th class="messageHeader" style="color:#208020;border:1px solid black;;background-color: #DDDDDD">' . i18n('colResultImport') . '</th></TR>';
			} else {
				$htmlResult.= '<TR>';
				if (count($fields) > count($title)) {
					$line="";
					foreach($fields as $field){
						$line.=$field." ;; ";
					}
					self::$cptError+=1;
					$htmlResult.= '<td colspan="' . count($title) . '" class="messageData" style="border:1px solid black;">';
					$htmlResult.= $line;
					$htmlResult.= '</td>';
					$htmlResult.= '<td class="messageData" style="border:1px solid black;">';
					$htmlResult.= '<div class="messageERROR" >ERROR : column count is incorrect</div>';
					$htmlResult.= '</td>';
					continue;
				}
				$id = ($idxId >= 0) ? pq_trim($fields[$idxId]) : null;
				if ($id and ! is_numeric($id)) {
				  self::$cptError+=1;
				  foreach($fields as $tmpIdx=>$tmpfield){
				    $htmlResult.='<td class="messageData" style="'.(($tmpIdx==$idxId)?'color:red;font-weight:bold':'').'">'.$tmpfield."</td>";
				  }
				  $htmlResult.= '<td class="messageData" style="border:1px solid black;">';
          $htmlResult.= '<div class="messageERROR" >'.i18n('messageInvalidNumeric',array('id')).'</div>';
          $htmlResult.= '</td>';
          continue;
				}
				if ($idxRefType>=0) {
				  $classTest=$fields[$idxRefType];
				  if($class==="ActivityWorkUnit"){
				    if(!$classTest)$classTest='Activity';
				  }
				  if (! SqlElement::class_exists($classTest)) {
				    foreach($fields as $tmpIdx=>$tmpfield){
				      $htmlResult.='<td class="messageData" style="'.(($tmpIdx==$idxRefType)?'color:red;font-weight:bold':'').'">'.$tmpfield."</td>";
				    }
				    self::$cptError+=1;
				    $htmlResult.= '<td class="messageData" style="border:1px solid black;">';
				    $htmlResult.= '<div class="messageERROR" >'.i18n('invalidClassName',array($classTest,' (refId)')).'</div>';
				    $htmlResult.= '</td>';
				    continue;
				  }
				}
				$obj = new $class($id);
				$refName='';
				$forceInsert = (!$obj->id and $id and !Sql::isPgsql()) ? true : false;
				self::$cptTotal+=1;
				foreach ($fields as $idx => $field) {
				  $fldName=$title[$idx];
				  if (isset($noImport[$idx])) {
						$htmlResult.= '<td class="messageData" style="color:'.$colorNoImport.';border:1px solid black;">' . htmlEncode($field) . '</td>';
						continue;
					}
					if ($fldName=='idPlanningMode') {
					  $fldName='id'.$class.'PlanningMode';
					}
					if (isset($titleObject[$idx])) {
					  $subClass = $titleObject[$idx];
						$subobj = new $subClass();
						$dataType = $subobj->getDataType($title[$idx]);
						$dataLength = $subobj->getDataLength($title[$idx]);
					} else {
						$dataType = $obj->getDataType($title[$idx]);
						$dataLength = $obj->getDataLength($title[$idx]);
					}
					if ($dataType == 'varchar') {
						if (pq_strlen($field) > $dataLength) {
							$field = pq_substr($field, 0, $dataLength);
						}
					}	else if ($dataType == 'date') { // 4.1.0 : Adaptation of date formats
						if (!$field == '') {
							if ($extension=="xlsx") {
							  if(is_numeric($field)) {
							    $field=date('Y-m-d',XLSXReader::toUnixTimeStamp($field));
							  }
							} else {
							  $field=formatBrowserDateToDate($field); // Detect if format is correct
							}
						}
					}	else if ($dataType=='datetime') { // 4.1.0 : Adaptation of date formats
						if (!$field == '') {
							if ($extension=="xlsx") {	
								$field=gmdate ('Y-m-d H:i:s',intval(XLSXReader::toUnixTimeStamp($field)));
							} else {
								$field=formatBrowserDateToDate($field); // Detect if format is correct
							}
						}
					} else if ($dataType == 'int' and ! isForeignKey($title[$idx]) ) { // --------------------------------------
					  if ($fldName=='refId' or $fldName=='ref1Id' or $fldName=='ref2Id' or $fldName=='predecessorRefId' or $fldName=='successorRefId') {
					    // Nothing, may contain Text
					  } else {
						  $field = pq_str_replace(' ', '', $field);
					  }
					} else if ($dataType == 'decimal') {
						$field=formatNumericInput($field);
					}
					if ($field == '') {
						$htmlResult.= '<td class="messageData" style="color:#000000;border:1px solid black;">' . htmlEncode($field) . '</td>';
						continue;
					}
					if (pq_strtolower($field) == 'null') {
						$field = null;
					}
					if ($idx == 0) {  
					  $abacusLineError = '';
					}
					if ($class == 'AbacusLine') {					  
					  $abacusClassNameMap = array('idClassName1' => 'className1','idClassName2' => 'className2','idClassName3' => 'className3','idClassName4' => 'className4','idClassName5' => 'className5');					  
					  if (isset($abacusClassNameMap[$fldName])) {				    
					    $classNameField = $abacusClassNameMap[$fldName];
					    $referencedClassName = null;
					    $resolvedId = null;
					    
					    if (property_exists($obj, 'idAbacusDefinition') && $obj->idAbacusDefinition) {
					      $abacusDef = new AbacusDefinition($obj->idAbacusDefinition);
					      if ($abacusDef && $abacusDef->id) $referencedClassName = $abacusDef->$classNameField;			      
					    }

					    if (!$referencedClassName || !SqlElement::class_exists($referencedClassName)) {
					      $htmlResult .= '<td class="messageData" style="color:red;border:1px solid black;">'. htmlEncode($field) . '</td>';
					      $abacusLineError = i18n('errorAbacusClassNotDefined', array($fldName, $classNameField));   
					      self::$cptError += 1;
					      continue;
					    }
              
					    if (is_numeric($field)) {
					      $fieldId = intval($field);
					      $testObj = new $referencedClassName($fieldId);
					      if ($testObj->id == $fieldId) {
					        // Valid ID
					        $resolvedId = $fieldId;
					        $obj->$fldName = $fieldId;
					        $htmlResult .= '<td class="messageData" style="color:#000000;border:1px solid black;">'. htmlEncode($field) . '</td>';
					      } else {
					        // Invalid ID
					        $htmlResult .= '<td class="messageData" style="color:red;border:1px solid black;">'. htmlEncode($field) . '</td>';
					        $abacusLineError = i18n('errorAbacusInvalidId', array($fieldId, $referencedClassName));  
					        self::$cptError += 1;
					      }
					    } else {
					      $resolvedId = SqlList::getIdFromName($referencedClassName, $field, false);
					      
					      if ($resolvedId) {
					        // Name Found
					        $obj->$fldName = $resolvedId;
					        $htmlResult .= '<td class="messageData" style="color:#008000;border:1px solid black;">'. htmlEncode($field) . ' ✓</td>';
					      } else {
					        // Name not found
					        $htmlResult .= '<td class="messageData" style="color:red;border:1px solid black;">'. htmlEncode($field) . '</td>';
					        $abacusLineError = i18n('errorAbacusNameNotFound', array($field, $referencedClassName));   
					        self::$cptError += 1;
					      }
					    }					    
					    continue;
					  }
					}
					
					if (pq_substr(pq_trim($field), 0, 1) == '"' and pq_substr(pq_trim($field), -1, 1) == '"') {
						$field = pq_substr(pq_trim($field), 1, pq_strlen(pq_trim($field)) - 2);
					}
					if ($idx == count($fields) - 1) {
						$field = pq_trim($field, "\r");
						$field = pq_trim($field, "\r\n");
					}
					$field = pq_str_replace('""', '"', $field);
					
					if (isset($titleObject[$idx])) {
					  $subClass = $titleObject[$idx];
					  if (!isset($obj->$subClass) or !is_object($obj->$subClass)) {
					    $obj->$subClass = new $subClass();
					  }
					  $sub = $obj->$subClass;
					  if (property_exists($subClass, $fldName)) {
					    if (isForeignKey($fldName) and ! is_numeric($field) and $field!=null) {
					      $clsSearch=pq_substr($fldName, 2);
					      if ($clsSearch=='Resource') $clsSearch='Affectable';
					      $obj->$subClass->$fldName = SqlList::getIdFromName($clsSearch, $field);
					    } else {
					      $obj->$subClass->$fldName = $field;
					    }
					    $htmlResult.= '<td class="messageData" style="color:#000000;border:1px solid black;">' . htmlEncode($field) . '</td>';
					    continue;
					  }
					} else if (property_exists($obj, $title[$idx])) {
					  if (isForeignKey($fldName) and ! is_numeric($field) and $field!=null) {
							if ($fldName=='idProject' or $fldName=='idActivity') {
							  $crit=array('name'=>$field);
							  if ($fldName=='idActivity' and property_exists($obj, 'idProject') and $obj->idProject) {
							    $crit['idProject']=$obj->idProject; // if project know, restrict to same project
							  }
							  $parentObj=SqlElement::getSingleSqlElementFromCriteria(pq_substr($fldName, 2), $crit);
							  if ($parentObj->id) { // Found and no dupplicate
							    $obj->$fldName= $parentObj->id;
							  }
							} else if ($fldName=='idDocumentDirectory') {
							  if (in_array('location',$title) and isset($fields[array_search('location',$title)]) and pq_trim($fields[array_search('location',$title)])!='' ) {
							    $obj->$fldName=null; // For document directory, do not search Parent Directory on name, as there may be dupplicates (on different location). If location is set, use it.
							  } else {
							    if (!isset($arrayLocation)) {
							      $arrayLocation=SqlList::getList('DocumentDirectory','location');
							    }
							    $idDD=array_search($field, $arrayLocation);
							    if ($idDD) {
							      $obj->$fldName=$idDD;
							    }
							  }
							} else {
							  //$clsSearch=pq_substr($fldName, 2);
							  $clsSearch=pq_substr(foreignKeyWithoutAlias($fldName), 2);
							  if ($clsSearch=='Resource') $clsSearch='Affectable';
							  if ($clsSearch=='Contact') $clsSearch='Affectable';
							  $oldVal=$obj->$fldName;
						    $obj->$fldName = SqlList::getIdFromName($clsSearch, $field, (($fldName=='id'.get_class($obj))?true:false));
						    if ($fldName=='idStatus' and $oldVal!=$obj->$fldName) $obj->recalculateCheckboxes(true);
							}
						} else if ( ($fldName=='refId' or $fldName=='ref1Id' or $fldName=='ref2Id' or $fldName=='predecessorRefId' or $fldName=='successorRefId') 
						            and $field!=null and !is_int($field)) {
						  $obj->$fldName=intval($field);
						  $classField=pq_substr($fldName,0,-2).'Type';
						  $idxRef=array_search($classField, $title);
						  $classRef=$fields[$idxRef]??null;
						  if (SqlElement::class_exists($classRef)) {
						    $crit=array('name'=>$field);
						    $refObj=SqlElement::getSingleSqlElementFromCriteria($classRef, $crit);
						    if ($refObj->id) { // Found and no dupplicate
						      $obj->$fldName=$refObj->id;
						    } 
						  }
						} else {
						  if(($fldName == 'work' or $fldName == 'leftWork' or pq_substr($fldName,-4)=='Work') and $convertWork){
						      $work = ($field/Work::getHoursPerDay());
						      $obj->$fldName = $work;
						    } else{
						      if ($fldName=='refType' and !Security::checkValidClass($field,false)){
						        $obj->$fldName = ' ' . $field . ' ';
						      }else {
						        $obj->$fldName = $field;
						      }
						    }
						}
						$htmlResult.= '<td class="messageData" style="color:#000000;border:1px solid black;">' . htmlEncode($field) . '</td>';
						continue;
					} else if ($field and $title[$idx]=='name' or $title[$idx]=='refName' or pq_strtolower($title[$idx])==pq_strtolower(i18n('name'))) {
					  $refName=$field;
					}
					$htmlResult.= '<td class="messageData" style="color:#A0A0A0;border:1px solid black;">' . htmlEncode($field) . '</td>';
					continue;
				}
				
				if (property_exists($obj, 'refType') and property_exists($obj, 'refId') and ! $obj->refId and $refName and Security::checkValidClass($obj->refType,false)) {
				  // refId not found but refName found : look for it !
				  $crit=array('name'=>$refName);
				  if (property_exists($obj, 'idProject') and property_exists($obj->refType, 'idProject') and $obj->idProject) {
				    $crit['idProject']=$obj->idProject;
				  }
				  $externalObj=SqlElement::getSingleSqlElementFromCriteria($obj->refType, $crit);
				  if ($externalObj and $externalObj->id) $obj->refId=$externalObj->id;
				}
				$htmlResult.= '<TD class="messageData" width="20%" style="border:1px solid black;">';
				//$obj->id=null;
				if ($forceInsert or !$obj->id) {
					if (property_exists($obj, "creationDate") and !pq_trim($obj->creationDate)) {
						$obj->creationDate = date('Y-m-d');
					}
					if (property_exists($obj, "creationDateTime") and !pq_trim($obj->creationDateTime)) {
						$obj->creationDateTime = date('Y-m-d H:i');
					}
				}
				Sql::beginTransaction();
				if (isset($obj->DocumentVersion)) {
				  $documentVersionObj=$obj->DocumentVersion;
				  unset($obj->DocumentVersion);
				}
				if ($class=="Work") {
				  $result = $obj->saveWork(); // Specific save method for import and API
				}else if ($class=="ImputationWork") {
				  $result = $obj->saveImputationWork(); // Specific save method for import and API
				}elseif($class==="ActivityWorkUnit"){
				  $result = $obj->saveActivityWorkUnit(); // Specific save method for import and API
				} else if ($forceInsert) { // object with defined id was not found : force insert
					$result = $obj->insert();
				} else {
					$result = $obj->save();
				}
				if (isset($documentVersionObj)) {
				  $documentVersionObj->idDocument=$obj->id;
				  $resultSub=$documentVersionObj->save();
				  $statusMain=getLastOperationStatus($result);
				  $statusSub=getLastOperationStatus($resultSub);
				  if ($statusMain=="ERROR" or $statusMain=="INVALID") {
				    // Will rollback
				  } else if ($statusMain=="OK") {
				    if ($statusSub=="ERROR" or $statusSub=="INVALID") {
				      $result=$resultSub; // Will rollback
				    } else if ($statusSub=="OK") {
				      $pos=pq_strpos($resultSub,'<input type="hidden" id="lastSaveId"');
				      if ($pos) {
				        $result=pq_str_replace('<input type="hidden" id="lastSaveId"', '<br/>'.pq_substr($resultSub,0,$pos).'<input type="hidden" id="lastSaveId"', $result);
				      }
				    }
				  } else  {
				    if ($statusSub=="ERROR" or $statusSub=="INVALID" or $statusSub=="OK") {
				      $result=$resultSub;
				    }
				  }
				}
				$resultStatus=getLastOperationStatus($result);
				traceLog("    => $resultStatus");
				if (!empty($abacusLineError)) {	  
				  Sql::rollbackTransaction();
				  $htmlResult.= '<div class="messageERROR" >' . $abacusLineError . '</div>';
				  $htmlResult.= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
				  $htmlResult.= '<input type="hidden" id="lastOperation" value="delete" />';
				  self::$cptInvalid+=1;				  
				} else if ($resultStatus=="ERROR") {
					Sql::rollbackTransaction();
					$htmlResult.= '<div class="messageERROR" >' . $result . '</div>';
					self::$cptError+=1;
				} else if ($resultStatus=="OK") {
					Sql::commitTransaction();
					$htmlResult.= '<div class="messageOK" >' . $result . '</div>';
					self::$cptOK+=1;
					if (pq_stripos($result, 'id="lastOperation" value="insert"') > 0) {
						self::$cptCreated+=1;
					} else if (pq_stripos($result, 'id="lastOperation" value="update"') > 0) {
						self::$cptModified+=1;
					} else {
						// ???
					}
				} else {
					Sql::commitTransaction();
					$htmlResult.= '<div class="message'.$resultStatus.'" >' . $result . '</div>';
					self::$cptWarning+=1;
					if ($resultStatus=="INVALID") {
						self::$cptInvalid+=1;
					} else if ($resultStatus=="NO_CHANGE") {
						self::$cptUnchanged+=1;
					} else {
						// ???
					}
				}
				$htmlResult.= '</TD></TR>';
			}
		}
		self::$cptDone=self::$cptCreated+self::$cptModified+self::$cptUnchanged;
		self::$cptRejected=self::$cptInvalid+self::$cptError;

		$htmlResult.= "</TABLE>";
		self::$importResult=$htmlResult;
		if (self::$cptError==0) {
			if (self::$cptInvalid==0) {
				$globalResult="OK";
			} else {
				$globalResult="INVALID";
			}
		} else {
			$globalResult="ERROR";
		}
		$log=new ImportLog();
		$log->name=basename($fileName);
		$log->mode="automatic";
		$log->importDateTime=date('Y-m-d H:i:s');
		$log->importFile=$fileName;
		$log->importClass=$class;
		$log->importStatus=$globalResult;
		$log->importTodo=self::$cptTotal;
		$log->importDone=self::$cptDone;
		$log->importDoneCreated=self::$cptCreated;
		$log->importDoneModified=self::$cptModified;
		$log->importDoneUnchanged=self::$cptUnchanged;
		$log->importRejected=self::$cptRejected;
		$log->importRejectedInvalid=self::$cptInvalid;
		$log->importRejectedError=self::$cptError;
		$log->save();
		self::stopImport();
		return $globalResult;
	}

	public static function importXLSX($fileName){
		require_once '../external/XLSXReader/XLSXReader.php';
		$xlsx = new XLSXReader($fileName);
		$sheetsList=$xlsx->getSheetNames();
		$sheet1Id=1;
		foreach ($sheetsList as $idS=>$nameS) {
		  $sheet1Id=$idS;
		  break;
		}
		$sheet1 = $xlsx->getSheet($sheet1Id);
		$data = $sheet1->getData();
		$xlsx->closeFile();
		return $data;
	}

	public static function importCSV($fileName) {
		$lines=file($fileName);
		$continuedLine="";
		$title=null;
		$csvSep=Parameter::getGlobalParameter('csvSeparator');
		if (!$csvSep) $csvSep=';';
		$data = array();
		$index=1;
		$utf8bom = "\xef\xbb\xbf";
		foreach ($lines as $nbl=>$line) {
		  $line=pq_str_replace($utf8bom,'',$line); // Remove unexpected BOM
			if (pq_trim($line)=='') {
				continue;
			}
			if (! mb_detect_encoding($line, 'UTF-8', true) ) {
			  $line=iconv('CP1252','UTF-8//TRANSLIT',$line);
			}
			if(!$title){
				if (function_exists('str_getcsv')) {
				  $title=str_getcsv($line,$csvSep,"\"","\\");
				} else {
					$title=pq_explode($csvSep,$line);
				}
				$data[0]=$title;
			}
			else{
				if ($continuedLine) {
					$line=$continuedLine.$line;
					$continuedLine="";
				}
				if (function_exists('str_getcsv')) {
				  $fields=str_getcsv($line,$csvSep,"\"","\\");
				} else {
					$fields=pq_explode($csvSep,$line);
				}
				if (count($fields)<count($title)) {
					$continuedLine=$line;
					continue;
				}

				$data[$index]=$fields;
				$index+=1;
			}
		}
		return $data;
	}
	public static function getLogHeader() {
		$nl=Parameter::getGlobalParameter('mailEol');
		$result="";
		$result.='<!DOCTYPE html>'.$nl;
		$result.='<html>'.$nl;
		$result.='<head>'.$nl;
		$result.='<meta charset="UTF-8"><meta http-equiv="content-type" content="text/html; charset=UTF-8" />'.$nl;
		$result.='<title>' . i18n("applicationTitle") . '</title>'.$nl;
		$result.='<style type="text/css">'.$nl;
		$result.='body{font-family:Verdana,Arial,Tahoma,sans-serif;font-size:8pt;}'.$nl;
		$result.='table{width:100%;border-collapse:collapse;border:1px;}'.$nl;
		$result.='.messageData{font-size:90%;padding:1px 5px 1px 5px;border:1px solid #AAAAAA;vertical-align:top;background-color:#FFFFFF;}'.$nl;
		$result.='.messageHeader{border:1px solid #AAAAAA;text-align:center;font-weight:bold;background:#DDDDDD;color:#505050;}';
		$result.='.messageERROR{color:red;font-weight:bold;}';
		$result.='.messageOK{color:green;}';
		$result.='.messageWARNING{color:black;}';
		$result.='</style>'.$nl;
		$result.='</head>'.$nl;
		$result.='<body style="font-family:Verdana,Arial,Tahoma,sans-serif;font-size:8pt;">'.$nl;
		return $result;
	}
	public static function getLogFooter() {
		$nl=Parameter::getGlobalParameter('mailEol');
		$nl=(isset($nl) and $nl)?$nl:"\r\n";
		$result="";
		$result.='</body>'.$nl;
		$result.='</html>';
		return $result;
	}
}

?>